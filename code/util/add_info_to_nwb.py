"""
Add metadata information to the NWB file.
"""

import json
import logging
from pathlib import Path
from typing import Union

from pynwb import NWBFile


def add_info_to_nwb(nwb: NWBFile, root_json_path: Union[str, Path]) -> NWBFile:
    """
    Adds metadata from JSON files in the specified root directory to the NWBFile object.

    Parameters
    ----------
    nwb : NWBFile
        The NWBFile object to which metadata will be added.

    root_json_path : Union[str, Path]
        The root directory where metadata JSON files (processing.json, session.json, procedures.json) are located.

    Returns
    -------
    NWBFile
        The updated NWBFile object with metadata added.
    """
    root_path = Path(root_json_path)

    # Add processing info
    processing_json_path = root_path / "processing.json"
    if processing_json_path.exists():
        with processing_json_path.open("r") as f:
            processing_json = json.load(f)
        nwb.data_collection = json.dumps(processing_json)
    else:
        logging.info("Processing JSON missing.")

    # Add lab and institute info
    nwb.lab = "AIND"

    # Add IACUC protocol from session file
    session_json_path = root_path / "acquisition.json"
    if session_json_path.exists():
        with session_json_path.open("r") as f:
            session_json = json.load(f)
        nwb.protocol = session_json.get("protocol_id", "")
    else:
        logging.info("IACUC protocol missing in session JSON.")

    # Add experimenter and surgery details from procedures file
    procedures_json_path = root_path / "procedures.json"
    if procedures_json_path.exists():
        with procedures_json_path.open("r") as f:
            procedures_json = json.load(f)

        subject_procedures = procedures_json.get("subject_procedures", [])
        if subject_procedures:
            nwb.Experimenter = subject_procedures[0].get("experimenter_full_name", "")
            nwb.surgery = "\n\n\n".join(json.dumps(p) for p in subject_procedures)
    else:
        logging.info("Procedures JSON file missing.")

    return nwb
