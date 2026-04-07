import argparse
import logging
import os
import subprocess
import time
from pathlib import Path

from ihb_common.utils.gen_utils import configure_logging

logger = logging.getLogger(__name__)


def main():
    """Main execution function with argparse and input type checking."""
    parser = argparse.ArgumentParser(description="Automatically selects and sets the best subtitle/CC stream as 'default' for supported files.")
    parser.add_argument("-i", "--input", type=str, help="The input path")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()
    configure_logging(level=args.level)

    INDETERMINATE_VALUES = ["unknown", "unspecified", "default"]

    color_parts = []
    color_parts.append(["-color_primaries", "test"])
    color_parts.append(["-color_trc", "UNKNOWN"])
    color_parts.append(["-colorspace", "JAZMYNE DAY"])
    color_parts.append(["-color_range", "DefAULT"])

    meaningful_color_parts = [item for sublist in color_parts for item in sublist if sublist[1].lower() not in INDETERMINATE_VALUES]

    print(meaningful_color_parts)


if __name__ == "__main__":
    main()
