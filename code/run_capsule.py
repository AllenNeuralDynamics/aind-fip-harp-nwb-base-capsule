"""top level run script"""

import argparse
import glob
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from hdmf_zarr import NWBZarrIO
from pydantic import Field
from pydantic_settings import BaseSettings

from aind_nwb_utils.utils import create_base_nwb_file
from util.add_fiber_to_nwb import (
    get_fiber_data_by_channel,
    add_fiber_data_to_nwb,
    deal_with_nans,
)
from util.add_info_to_nwb import add_info_to_nwb


class FiberSettings(BaseSettings, cli_parse_args=True):
    """
    Settings for Fiber Photometry
    """

    input_directory: Path = Field(
        default=Path("/data"), description="Directory where data is"
    )
    output_directory: Path = Field(
        default=Path("/results/"), description="Output directory"
    )
if __name__ == "__main__":
    settings = FiberSettings()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    logging.info(f"Fiber Settings, {settings.model_dump()}")
    fiber_fp = settings.input_directory / "fiber_raw_data"
    # Load subject data
    subject_json_path =  fiber_fp / "subject.json"
    with subject_json_path.open("r") as f:
        subject_data = json.load(f)

    subject_id = subject_data.get("subject_id", None)

    # Load data description
    data_description_path = fiber_fp / "data_description.json"
    with data_description_path.open("r") as f:
        date_data = json.load(f)

    session_path = fiber_fp / "acquisition.json"
    with session_path.open("r") as f:
        session_data = json.load(f)
    date = session_data["acquisition_start_time"]

    asset_name = date_data["name"]

    nwb_filename = f"{asset_name}.nwb"
    nwb_output_path = settings.output_directory / "nwb"
    nwb_output_path.mkdir(parents=True, exist_ok=True)

    base_nwb_file = create_base_nwb_file(fiber_fp)

    if not [i for i in fiber_fp.glob("fib/")]:
        raise ValueError("No fiber data detected")

    fiber_directories = [i for i in fiber_fp.glob("fib/*") if i.is_dir()]
    if not fiber_directories:
        raise FileNotFoundError("No fiber data found. Check asset")
    
    logging.info("Standard file format detected")
    fiber_channel_data = get_fiber_data_by_channel(fiber_directories[0])
    fiber_channel_data_cleaned_for_nans = deal_with_nans(fiber_channel_data)
    nwbfile = add_fiber_data_to_nwb(
        base_nwb_file, fiber_channel_data_cleaned_for_nans
    )

    nwbfile = add_info_to_nwb(nwbfile, fiber_fp)
    nwb_output_fn = nwb_output_path / nwb_filename

    with NWBZarrIO(path=nwb_output_fn.as_posix(), mode="w") as io:
        io.write(nwbfile)

        logging.info("Successfully wrote NWB file.")

