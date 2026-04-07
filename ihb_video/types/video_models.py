import re
from dataclasses import dataclass
from math import gcd
from typing import Any

from humanfriendly import format_size

from ihb_common.utils.gen_utils import format_time
from ihb_video.types.stream_models import StreamType

PSNR_COMP_REGEX = re.compile(r"PSNR y:(.*?)\s+u:(.*?)\s+v:(.*?)\s+average:(.*?)\s+min:(.*?)\s+max:(.*)")
FLOAT_REGEX = re.compile(r"^\d*\.?\d+$")


def _str_to_float(in_str: str) -> float:
    return float(in_str) if FLOAT_REGEX.match(in_str) else -1 if in_str.lower() == "inf" else -2


def _float_to_str(in_float: float) -> str:
    return "inf" if in_float == -1 else "err" if in_float == -2 else f"{in_float:.02f}"


class Resolution:
    width: int
    height: int
    is_landscape: bool

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.is_landscape = width >= height

    def __str__(self):
        return self.get_resolution_str(True)

    def get_aspect_ratio_num(self) -> float:
        aspect_ratio = self.width / self.height if self.is_landscape else self.height / self.width
        return aspect_ratio

    def get_resolution_str(self, include_tag: bool = False):
        w = "w" if include_tag else ""
        h = "h" if include_tag else ""
        return f"{self.width}{w} x {self.height}{h}"

    def get_area(self) -> int:
        return self.width * self.height

    def get_aspect_ratio_str(self):
        return get_aspect_ratio_str(self.width, self.height)


class FrameTimeData:
    time_code: float

    def __init__(self, input_dict: dict[str, Any]):
        self.time_code = float(input_dict.get("pts_time") or input_dict.get("best_effort_timestamp_time"))

    def __str__(self):
        return str(self.time_code)


class PsnrComparison:
    luminence: float
    cb: float
    cr: float
    average: float
    min: float
    max: float

    def __init__(self, input_str: str):
        psnr_match = PSNR_COMP_REGEX.search(input_str)
        if psnr_match:
            groups = psnr_match.groups()
            self.luminence = _str_to_float(groups[0])
            self.cb = _str_to_float(groups[1])
            self.cr = _str_to_float(groups[2])
            self.average = _str_to_float(groups[3])
            self.min = _str_to_float(groups[4])
            self.max = _str_to_float(groups[5])

    def get_display_string(self) -> str:
        disp_str = f"avg: {_float_to_str(self.average)}" f" min: {_float_to_str(self.min)}" f" max: {_float_to_str(self.max)}"

        return disp_str


def get_aspect_ratio_str(width: int, height: int):
    calc_gcd = gcd(width, height)
    ar_width = width // calc_gcd
    ar_height = height // calc_gcd

    return f"{ar_width}:{ar_height}"


@dataclass
class VideoMetrics:

    LABELS = [
        "Name",
        "Profile",
        "Codec",
        "Color Profile",
        "Duration",
        "Aspect Ratio",
        "Size",
        "Resolution",
        "BPPF",
        "V_Bitrate",
        "A_Bitrate",
    ]

    name: str
    profile: str
    codec: str
    color_format: str
    duration: float
    size: int
    resolution: Resolution
    bppf: float
    v_bitrate: float
    a_bitrate: float

    @classmethod
    def from_ffprobe_data(cls, probe_data: dict[str, Any], profile, is_set_bitrate: bool) -> VideoMetrics:
        from ..utils.video_utils import calc_bitrate, calc_bppf

        format_data = probe_data["format_data"]
        video_data = probe_data["v_streams"][0]
        audio_data = probe_data["a_streams"][0] if probe_data["a_count"] > 0 else {}
        data = {}

        data["name"] = format_data["filename"]
        data["profile"] = profile

        audio_codec = audio_data.get("codec_name", "NO AUDIO")
        audio_rate = f" @ {int(audio_data.get('sample_rate', 0))//1000}k" if probe_data["a_count"] > 0 else ""

        data["codec"] = f"{video_data["codec_name"]} : {audio_codec}{audio_rate}"
        data["color_format"] = video_data.get("pix_fmt", "N/A")

        data["duration"] = float(format_data["duration"])
        data["size"] = int(format_data["size"])

        data["resolution"] = Resolution(video_data["width"], video_data["height"])
        data["bppf"] = calc_bppf(probe_data)

        data["v_bitrate"] = calc_bitrate(probe_data, StreamType.VIDEO) if is_set_bitrate else -1
        data["a_bitrate"] = calc_bitrate(probe_data, StreamType.AUDIO) if is_set_bitrate and audio_data else -1

        video_metrics = cls(**data)
        return video_metrics

    def to_pretty_list(self) -> list[str]:
        from ..utils.video_utils import format_bitrate

        class_data = []

        class_data.append(self.name)
        class_data.append(self.profile.name if self.profile else "N/A")
        class_data.append(self.codec)
        class_data.append(self.color_format)
        class_data.append(format_time(self.duration))
        class_data.append(f"{self.resolution.get_aspect_ratio_str()}  : {self.resolution.get_aspect_ratio_num():.02f}")
        class_data.append(format_size(self.size))
        class_data.append(self.resolution.get_resolution_str(True))
        class_data.append(f"{self.bppf:.02f}")
        class_data.append(format_bitrate(self.v_bitrate))
        class_data.append(format_bitrate(self.a_bitrate))

        return class_data

    def compare_to(self, new_metrics: VideoMetrics) -> list[str]:
        from ..utils.video_utils import format_bitrate

        comp_data = ["--"] * len(VideoMetrics.LABELS)

        comp_data[VideoMetrics.LABELS.index("Duration")] = f"{(self.duration - new_metrics.duration):.04f}"

        comp_data[VideoMetrics.LABELS.index("Aspect Ratio")] = (
            f"{(self.resolution.get_aspect_ratio_num() - new_metrics.resolution.get_aspect_ratio_num()):.04f}"
        )

        size_delta = self.size - new_metrics.size
        sign_delta = "-" if size_delta < 0 else ""
        size_reduction = 100 * (1 - (new_metrics.size / self.size))
        comp_data[VideoMetrics.LABELS.index("Size")] = f"{sign_delta}{format_size(abs(size_delta))} : {size_reduction:.02f}%"

        area_delta = 100 * (1 - (new_metrics.resolution.get_area() / self.resolution.get_area()))
        comp_data[VideoMetrics.LABELS.index("Resolution")] = f"{area_delta:.02f}%"

        comp_data[VideoMetrics.LABELS.index("BPPF")] = f"{(self.bppf - new_metrics.bppf):.02f} : {100 * (1 - (new_metrics.bppf / self.bppf)):.02f}%"

        if self.v_bitrate > 0 and new_metrics.v_bitrate > 0:
            comp_data[VideoMetrics.LABELS.index("V_Bitrate")] = (
                f"{format_bitrate(self.v_bitrate - new_metrics.v_bitrate)} : {100 * (1 - (new_metrics.v_bitrate / self.v_bitrate)):.02f}%"
            )

        if self.a_bitrate > 0 and new_metrics.a_bitrate > 0:
            comp_data[VideoMetrics.LABELS.index("A_Bitrate")] = (
                f"{format_bitrate(self.a_bitrate - new_metrics.a_bitrate)} : {100 * (1 - (new_metrics.a_bitrate / self.a_bitrate)):.02f}%"
            )

        return comp_data

    @classmethod
    def get_data_labels(cls) -> list[str]:
        return cls.LABELS.copy()


@dataclass
class ValidationResultDTO:
    test_name: str
    result: bool
    message: str

    def __str__(self):
        return f"test {self.test_name} || {"PASS" if self.result else "FAIL"} || {self.message}"

    def __repr__(self):
        return self.__str__()
