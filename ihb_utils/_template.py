import argparse
import logging

from ihb_utils.gen_utils import configure_logging

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", type=str, help="The input path")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()

    configure_logging(level=args.level)


if __name__ == "__main__":
    main()
