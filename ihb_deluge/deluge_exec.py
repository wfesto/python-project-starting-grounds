import logging
import logging.config
import os
import re
import sys
import time

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.append(root_dir)


from ihb_utils.file_utils import load_config
from ihb_utils.gen_utils import format_time
from ihb_video.cc_default_setter import process_directory, process_file

logger = logging.getLogger(__name__)


def main():
    config_path = os.path.join(os.path.dirname(__file__), "conf")

    log_config_file_path = os.path.join(config_path, "logging.ini")
    logging.config.fileConfig(log_config_file_path, disable_existing_loggers=False)

    config = load_config(file_path=config_path)

    logger.info(f'{"-" * 5} Starting Processing - {__file__}  {"-" * 5}')
    logger.info(f"Calling parameters: {sys.argv}")

    torrent_id = sys.argv[1]
    torrent_name = sys.argv[2]
    torrent_dir = sys.argv[3]

    check_dir = torrent_dir.replace("\\", "/")
    if found_dir := next((dir for dir in config["skip_dirs"] if str.lower(dir) in check_dir.lower()), None):
        logger.info(f"Skipping {torrent_dir} because it matches {found_dir}")
        return 0

    if name_match := next((name for name in config["skip_names"] if re.search(str.lower(name), torrent_name.lower())), None):
        logger.info(f"Skipping {torrent_name} because it matches {name_match}")
        return 0

    potential_file_path = os.path.join(torrent_dir, torrent_name)

    start_time = time.perf_counter()
    if os.path.exists(potential_file_path):
        if os.path.isfile(potential_file_path):
            logger.info(f" -> Single file: {potential_file_path}")
            process_file(potential_file_path)

        elif os.path.isdir(potential_file_path):
            logger.info(f" -> Directory: {potential_file_path}")
            process_directory(potential_file_path, proc_subs=True)

        else:
            logger.warning(f"Unable to process {potential_file_path}")

    else:
        logger.info("Skipping - Probably a deleted torrent.")
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    logger.info(f"Processing took {format_time(elapsed_time)}")


if __name__ == "__main__":
    main()
