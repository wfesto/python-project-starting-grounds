import logging
import os
import sys
from typing import Any, Dict

from ihb_utils.file_utils import load_config

logger = logging.getLogger(__name__)
_CONFIG_DATA = None


def get_config() -> Dict[str, Any]:
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

        _CONFIG_DATA["db_conn"] = os.path.join(potential_path, db_config["file"])

    return _CONFIG_DATA
