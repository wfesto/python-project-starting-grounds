import logging
import os
import sys
from typing import Any, Dict

from ihb_common.utils.file_utils import load_config

logger = logging.getLogger(__name__)
_CONFIG_DATA = None

_CONFIG_DEFAULTS = {
    "general": {
        "hash_partial": True,
        "max_workers": 4,
    },
    "db": {
        "path": "db",
        "file": "ihb_video_tools.db",
        "cache": 25,
        "writer_sleep": 2,
    },
    "duplicate": {
        "radius": 0.5,
    },
}


def get_config():
    global _CONFIG_DATA

    if not _CONFIG_DATA:
        _CONFIG_DATA = load_config(file_path=os.path.dirname(__file__))
        db_config = _CONFIG_DATA["db"]
        potential_path = db_config["path"]
        if not os.path.isdir(potential_path):
            potential_path = os.path.join(os.path.dirname(__file__), "..", potential_path)
            if not os.path.isdir(potential_path):
                logger.critical(f"Invalid db path config: {db_config['path']}")
                sys.exit(1)

        db_config["conn"] = os.path.join(potential_path, db_config["file"])
        _CONFIG_DATA["db_conn"] = db_config["conn"]

    return _CONFIG_DATA
