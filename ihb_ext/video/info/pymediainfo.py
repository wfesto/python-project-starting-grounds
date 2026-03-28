import logging
import os
import sys

from pymediainfo import *

logger = logging.getLogger(__name__)


def get_video_metadata(file_path: str) -> dict[str, Any]:
    if not os.path.exists(file_path):
        logger.warning(f"{file_path} does not exist")
        return

    media_info = MediaInfo.parse(file_path)

    file_dict = {
        "format_data": media_info.general_tracks[0].to_data(),
        "v_count": len(media_info.video_tracks),
        "v_streams": [track.to_data() for track in media_info.video_tracks],
        "a_count": len(media_info.audio_tracks),
        "a_streams": [track.to_data() for track in media_info.audio_tracks],
        "s_count": len(media_info.text_tracks),
        "s_streams": [track.to_data() for track in media_info.text_tracks],
    }

    return file_dict


def is_video_file(file_path: str) -> bool:
    if not os.path.exists(file_path):
        logger.warning(f"{file_path} does not exist")
        return False

    media_info = MediaInfo.parse(file_path)
    return bool(media_info.video_tracks)


def main(path: str):
    media_info = MediaInfo.parse(path)
    full_data_json = media_info.to_json()
    print(full_data_json)


if __name__ == "__main__":
    main(sys.argv[1])
