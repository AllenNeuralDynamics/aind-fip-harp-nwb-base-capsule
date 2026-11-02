import logging
import re
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd
import pynwb
from hdmf_zarr import NWBZarrIO


CHANNEL_MAPPING = {"red": "R", "green": "G", "iso": "Iso"}

# Each pattern captures the index in group 1, e.g. match.group(1) is "10" for "ROI_10"
# ROI columns are named ROI_<n> in the current file standard, Fiber_<n> in older sessions
ROI_COLUMN_PATTERN = re.compile(r"^ROI_(\d+)$")
LEGACY_ROI_COLUMN_PATTERN = re.compile(r"^Fiber_(\d+)$")
PATCH_CORD_PATTERN = re.compile(r"^Patch Cord (\d+)$")
FIBER_PATTERN = re.compile(r"^Fiber[ _](\d+)$")


def get_implanted_fibers(procedures: dict) -> set[int]:
    """
    Get the indices of the fibers implanted according to the procedures metadata.

    Parameters
    ----------
    procedures : dict
        Contents of procedures.json

    Returns
    -------
    set[int]
        Indices of implanted fibers, e.g. {0, 1} for Fiber_0 and Fiber_1
    """
    implanted_fibers = set()
    for subject_procedure in procedures.get("subject_procedures", []):
        if subject_procedure.get("object_type") != "Surgery":
            continue

        for procedure in subject_procedure.get("procedures", []):
            implanted_device = procedure.get("implanted_device") or {}
            if implanted_device.get("object_type") != "Fiber probe":
                continue

            match = FIBER_PATTERN.match(implanted_device.get("name", ""))
            if match:
                implanted_fibers.add(int(match.group(1)))

    return implanted_fibers


def get_roi_to_fiber_mapping(
    acquisition: dict, procedures: dict
) -> dict[int, int]:
    """
    Map each ROI to the fiber it recorded from, using the patch cord to
    fiber connections in the acquisition metadata. Patch Cord N corresponds
    to ROI N.

    Parameters
    ----------
    acquisition : dict
        Contents of acquisition.json
    procedures : dict
        Contents of procedures.json. ROIs connected to fibers that were
        not implanted are dropped.

    Returns
    -------
    dict[int, int]
        Mapping of ROI index to fiber index

    Raises
    ------
    ValueError
        If the acquisition has no patch cord to fiber connections, or
        procedures has no implanted fibers
    """
    roi_to_fiber = {}
    for data_stream in acquisition.get("data_streams", []):
        for connection in data_stream.get("connections", []):
            patch_cord = PATCH_CORD_PATTERN.match(connection.get("source_device", ""))
            fiber = FIBER_PATTERN.match(connection.get("target_device", ""))
            if patch_cord and fiber:
                roi_to_fiber[int(patch_cord.group(1))] = int(fiber.group(1))

    if not roi_to_fiber:
        raise ValueError(
            "No patch cord to fiber connections found in acquisition metadata. "
            "Cannot map ROIs to fibers"
        )

    implanted_fibers = get_implanted_fibers(procedures)
    if not implanted_fibers:
        raise ValueError(
            "No implanted fibers found in procedures metadata. "
            "Cannot check ROIs against implanted fibers"
        )

    for roi, fiber in list(roi_to_fiber.items()):
        if fiber not in implanted_fibers:
            logging.warning(
                f"ROI {roi} is connected to fiber {fiber}, which is not "
                f"implanted according to procedures. Skipping ROI {roi}"
            )
            del roi_to_fiber[roi]

    logging.info(f"ROI to fiber mapping: {roi_to_fiber}")
    return roi_to_fiber


def first_nan_idx(arr: np.ndarray, axis: int = -1) -> int:
    """
    Find the index of the first NaN along the specified axis.

    Parameters:
    arr (np.ndarray): Input array.
    axis (int): Axis along which to find the first NaN.

    Returns:
    int: Index of the first NaN along the specified axis, or -1 if no NaN is found.
    """
    is_nan = np.isnan(arr)
    if not np.any(is_nan):
        return -1
    first_nan_idx = np.argmax(is_nan, axis=axis)
    return min(first_nan_idx[np.any(is_nan, axis=-1)])


def deal_with_nans(
    dict_fip: dict, check_both: bool = True, max_drop: int = 3600
) -> dict:
    """
    Handle NaNs and length differences in a dictionary of data traces, automatically ignoring header rows.

    Parameters:
    dict_fip (dict): Keys -> identifiers, values -> 2D numpy arrays (rows, T)
    check_both (bool): If True, check both rows for NaNs; else only second row (signal)
    max_drop (int): Maximum number of samples to drop from the end if NaNs found near the end

    Returns:
    dict: Dictionary with traces truncated to remove NaNs.
    """
    # --- Detect header rows ---
    skip_rows = 0
    first_key = next(iter(dict_fip))
    arr = dict_fip[first_key]

    for row in range(arr.shape[0]):
        row_data = arr[row, :]
        # If any element is not numeric, treat as header
        if not np.all(
            [isinstance(x, (int, float, np.integer, np.floating)) for x in row_data]
        ):
            skip_rows += 1
        else:
            break

    if skip_rows > 0:
        logging.info(f"Detected {skip_rows} header row(s), ignoring them in NaN check.")

    # --- Compute first NaN index ignoring header rows ---
    first_nan_list = []
    for k, arr in dict_fip.items():
        if check_both:
            data_to_check = arr[skip_rows:, :]
        else:
            # Only the first non-header row (signal)
            data_to_check = arr[skip_rows : skip_rows + 1, :]
        nan_idx = first_nan_idx(data_to_check)
        first_nan_list.append(nan_idx)

    first_nan_arr = np.array(first_nan_list)
    first_nan = (
        -1 if np.all(first_nan_arr == -1) else min(first_nan_arr[first_nan_arr > -1])
    )

    # --- Determine truncation length ---
    n_frames = [dict_fip[k].shape[1] for k in dict_fip.keys()]
    min_len, max_len = min(n_frames), max(n_frames)

    if min_len < max_len - max_drop:
        logging.warning(f"Shortest/longest trace has {min_len}/{max_len} frames.")

    if first_nan == -1:
        new_len = min_len
    elif first_nan > min_len - max_drop:
        new_len = min(min_len, first_nan)
        logging.warning(
            f"Trace includes NaN near the end. Dropping last {min_len - new_len} frames."
        )
    else:
        new_len = min_len
        logging.warning(f"Trace includes NaN in the middle.")

    # --- Truncate traces ---
    for k in dict_fip.keys():
        dict_fip[k] = dict_fip[k][:, :new_len]

    return dict_fip


def get_roi_columns(columns: pd.Index, pattern: re.Pattern) -> dict[str, int]:
    """
    Get the ROI columns matching a naming pattern.

    Parameters
    ----------
    columns : pd.Index
        Columns of a channel CSV
    pattern : re.Pattern
        Pattern with one group capturing the ROI index

    Returns
    -------
    dict[str, int]
        Mapping of column name to ROI index
    """
    roi_columns = {}
    for column in columns:
        match = pattern.match(column)
        if match:
            roi_columns[column] = int(match.group(1))

    return roi_columns


def get_fiber_data_by_channel(
    session_fiber_directory: Path, roi_to_fiber: dict[int, int]
) -> dict[str, np.ndarray]:
    """
    Load fiber photometry data for each channel from a session directory.

    Parameters
    ----------
    session_fiber_directory : Path
        Path to the directory containing fiber photometry data files for the session.
    roi_to_fiber : dict[int, int]
        Mapping of ROI index to fiber index. ROIs not in the mapping are skipped.

    Returns
    -------
    dict[str, np.ndarray]
        A dictionary mapping channel name and fiber index to their corresponding
        timeseries data.
    """
    fiber_timeseries = {}

    for channel in CHANNEL_MAPPING:
        channel_path = session_fiber_directory / f"{channel}.csv"
        if not channel_path.exists():
            raise FileNotFoundError(f"No {channel} data found in fiber directory")

        df_channel = pd.read_csv(session_fiber_directory / f"{channel}.csv")
        timestamps = df_channel["ReferenceTime"].to_numpy()

        roi_columns = get_roi_columns(df_channel.columns, ROI_COLUMN_PATTERN)
        if not roi_columns:
            roi_columns = get_roi_columns(df_channel.columns, LEGACY_ROI_COLUMN_PATTERN)
            if not roi_columns:
                raise ValueError(f"No ROI_<n> or Fiber_<n> columns found in {channel}.csv")
            logging.info(f"Using legacy Fiber_<n> columns as ROIs in {channel}.csv")

        for column, roi in roi_columns.items():
            if roi in roi_to_fiber:
                index = roi_to_fiber[roi]
            else:
                logging.warning(
                    f"Skipping {channel} {column}. ROI not mapped to a fiber in acquisition"
                )
                continue

            data = df_channel[column].to_numpy()
            is_all_nan = np.isnan(data).all()
            is_all_zero = np.all((data == 0) | np.isnan(data)) and not is_all_nan
            if is_all_nan or is_all_zero:
                logging.warning(
                f"Skipping fiber {channel}_{index}. All nan or 0s"
                )
                continue

            fiber_timeseries[f"{CHANNEL_MAPPING[channel]}_{index}"] = np.array(
                [timestamps, data]
            )

    return fiber_timeseries


def add_fiber_data_to_nwb(nwb: pynwb.NWBFile, dict_fip: dict) -> pynwb.NWBFile:
    """
    Attach FIP data to an existing NWB file.

    Parameters:
    nwb: pynwb.NWBFile 
        The NWB file to add
    dict_fip: dict
         A dictionary containing the FIP data.

    Returns:
    pynwb.NWBFile: The updated NWB file with the attached FIP data.
    """
    logging.info(f"dict_fip {dict_fip}")

    for neural_stream in dict_fip:
        full_channel = neural_stream
        channel_key = full_channel[0 : full_channel.index("_")]
        channel = next((k for k, v in CHANNEL_MAPPING.items() if v == channel_key))

        if 'CMOS' in neural_stream:
            description = f"{channel} CMOS floor signal"
        else:
            fiber_index = neural_stream[neural_stream.index("_") + 1 :]
            description = f"{channel} channel for fiber {fiber_index} using 0-based indexing"

        ts = pynwb.TimeSeries(
            name=neural_stream,
            data=dict_fip[neural_stream][1],
            unit="s",
            timestamps=dict_fip[neural_stream][0],
            description=description
        )
        logging.info(f"Shape of timeseries data in nwb {ts.data.shape}")
        nwb.add_acquisition(ts)

    return nwb
