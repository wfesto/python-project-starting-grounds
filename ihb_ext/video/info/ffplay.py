import logging
import shlex

from ihb_common.utils.gen_utils import _run_simple_cli_command
from ihb_video.types.video_models import Resolution

logger = logging.getLogger(__name__)

FFPLAY_BINARY = "ffplay"


def play_video(input_file: str, vol_level: int = 50) -> int:
    command = [
        FFPLAY_BINARY,
        "-i",
        input_file,
        "-af",
        f'"volume=0.{vol_level}"',
    ]

    result = _run_simple_cli_command(command)
    if result:
        result.returncode
    else:
        return -1


def play_videos_comparison(input_file_one: str, input_file_two: str, vol_level: int = 50, resolution: Resolution = Resolution(480, 848)) -> int:

    santz_f1 = input_file_one.replace(":", "\\:")
    santz_f2 = input_file_two.replace(":", "\\:")

    command = [
        FFPLAY_BINARY,
        "-f",
        "lavfi",
        "-i",
        f"""movie='{santz_f1}'[v0]; movie='{santz_f2}'[v1]; [v0][v1]scale2ref=oh*mdar:ih[v0s][v1]; [v0s][v1]hstack=inputs=2""",
        #        "-af",
        #       f'"volume=0.{vol_level}"',
    ]

    result = _run_simple_cli_command(command)
    if result:
        result.returncode
    else:
        return -1


def main(): ...


if __name__ == "__main__":
    main()
