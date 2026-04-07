import argparse
import logging
import os

from ihb_common.utils.gen_utils import VERBOSE_LEVEL_NUM, configure_logging
from ihb_video.manager import video_manager
from ihb_video.types.stream_models import StreamType
from ihb_video.utils.stream_utils import *

logger = logging.getLogger(__name__)


def _get_default_audio_stream(probe_data: dict[str, Any]) -> dict[str, Any]:
    if probe_data["a_count"] > 1:
        eng_streams = filter_streams_eng(probe_data["a_streams"])
        if len(eng_streams) == 1:
            logger.info(f"Audio stream chosen: {get_stream_desc(eng_streams[0])}")
            return eng_streams[0]


def _get_default_subtitle_stream(probe_data: dict[str, Any]) -> dict[str, Any]:
    if probe_data["s_count"] == 0:
        logger.warning("No subtitles available")
        return

    sub_streams = probe_data["s_streams"]

    chosen_stream = None
    chosen_method = None

    eng_subtitle_streams = filter_streams_eng(sub_streams)
    und_subtitle_streams = filter_streams_unknown(sub_streams)

    if eng_subtitle_streams:
        chosen_stream, chosen_method = _get_best_subtitle_stream(eng_subtitle_streams, "English")

    elif und_subtitle_streams:
        chosen_stream, chosen_method = _get_best_subtitle_stream(und_subtitle_streams, "Unknown")

    if not chosen_stream:
        chosen_stream = sub_streams[0]
        chosen_method = "First stream"

    logger.info(f"Subtitle stream chosen: {get_stream_desc(chosen_stream)} via {chosen_method}")

    return chosen_stream


def _get_best_subtitle_stream(sub_streams: list, keyword: str) -> tuple[dict[str, Any], str]:
    """
    Selects the best subtitle stream index, looking at english strams, then unknown streams
    Returns the selected stream index and method of choosing, or None
    """
    chosen_stream = None
    chosen_method = None

    if sub_streams:
        chosen_stream = next((stream for stream in sub_streams if stream.get("disposition", {}).get("hearing_impaired", 0) == 1), None)
        chosen_method = f"disposition.hearing_impaired + {keyword}"

        if not chosen_stream:
            chosen_stream = next((stream for stream in sub_streams if "sdh" in get_stream_tag(stream, "title").lower()), None)
            chosen_method = f"SDH + {keyword}"

        if not chosen_stream:
            potential_stream = max(sub_streams, key=get_stream_size_est)
            chosen_stream = potential_stream if get_stream_size_est(potential_stream) > 0 else None
            chosen_method = f"Largest-ish {keyword}"

        if not chosen_stream:
            chosen_stream = sub_streams[0]
            chosen_method = f"First {keyword}"

    return chosen_stream, chosen_method


def process_file(input_file: str, *stream_type_list: StreamType) -> bool:
    file_name = os.path.basename(input_file)
    logger.info(f"Processing: {file_name}")

    probe_data = video_manager.get_video_metadata(input_file)

    for stream_type in stream_type_list:
        try:
            stream_chooser = None
            match stream_type:
                case StreamType.AUDIO:
                    stream_chooser = _get_default_audio_stream
                case StreamType.SUBTITLE:
                    stream_chooser = _get_default_subtitle_stream
                case _:
                    logger.warning(f"No stream selection logic implemented for stream type {stream_type.name}")
                    continue

            if new_default_stream := stream_chooser(probe_data):
                logger.info(f" --> {stream_type.name} stream {new_default_stream["index"]} chosen")
                if new_default_stream.get("disposition", {}).get("default", 0) == 1:
                    logger.info(" --> Stream is already default, skipping.")
                else:
                    stream_key = stream_type.name[0].lower()
                    if old_default_stream := next((s for s in probe_data[f"{stream_key}_streams"] if s.get("disposition", {}).get("default") == 1), None):
                        video_manager.update_default_stream(
                            file_path=input_file, probe_data=probe_data, selected_index=old_default_stream["index"], is_default=False, stream_type=stream_type
                        )

                    video_manager.update_default_stream(
                        file_path=input_file, probe_data=probe_data, selected_index=new_default_stream["index"], is_default=True, stream_type=stream_type
                    )

            else:
                logger.log(VERBOSE_LEVEL_NUM, f"{input_file} doesn't select a new {stream_type.name} stream.")
        except Exception as e:
            logger.error(f"Error encountered during stream type {stream_type.name} : {e}", exc_info=True)

    return True


def process_directory(input_dir: str, *stream_type: StreamType) -> int:
    logger.info(f"--- Starting in Dir: {input_dir}")
    processed_count = 0

    for dir_name, _, file_list in os.walk(input_dir):
        for file_name in file_list:
            file_path = os.path.join(dir_name, file_name)
            logger.info(file_path)

            if video_manager.is_supported_file(file_name):
                if process_file(file_path, *stream_type):
                    processed_count += 1
                else:
                    logger.warning(" -> File not processed / processing unsuccessful")
            else:
                logger.log(VERBOSE_LEVEL_NUM, f" -> Skipping {file_name}, unsupported file type")

    logger.info(f"--- {stream_type} Default Processing Complete for {input_dir}. Total files updated: {processed_count} ---")
    return processed_count


def process_path(input_path: str, *stream_type: StreamType) -> int:
    if not input_path and not os.path.exists(input_path):
        logger.error(f"{input_path} does not exist. Exiting.")
        return -1

    if os.path.isdir(input_path):
        return process_directory(input_path, *stream_type)
    elif os.path.isfile(input_path):
        return process_file(input_path, *stream_type)
    else:
        logger.error(f"Invalid file or directory path: {input_path}")
        return -1


def main():
    parser = argparse.ArgumentParser(description="Automatically selects and sets the best subtitle/CC stream as 'default' for supported files.")
    parser.add_argument("-i", "--input", type=str, help="The input path. Can be a single file or a directory")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()

    configure_logging(level=args.level)

    input_path = args.input
    if not input_path:
        logger.error("No valid input path provided. Exiting.")
        return 1

    processed_files = process_path(args.input, StreamType.AUDIO, StreamType.SUBTITLE)
    if processed_files < 0:
        logger.error("Error encountered during processing.")
    else:
        logger.info(f"{processed_files} files successfully processed.")


if __name__ == "__main__":
    main()
