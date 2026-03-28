import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VideoDataDTO:
    file_name: str
    file_path: str
    size_b: int
    duration_ms: float
    has_audio: bool
    has_subs: bool

    @classmethod
    def from_pymediainfo_data(cls, file_path: str, tool_data: dict):
        intr_data: dict = {}
        # intr_data[""] =

        format_data = tool_data["format_data"]

        intr_data["file_name"] = os.path.basename(file_path)
        intr_data["file_path"] = file_path
        intr_data["size_b"] = int(format_data["file_size"])
        intr_data["duration_ms"] = format_data["duration"]
        intr_data["has_audio"] = int(tool_data["a_count"]) > 0
        intr_data["has_subs"] = int(tool_data["s_count"]) > 0

        video_dto = cls(**intr_data)
        return video_dto

    @classmethod
    def from_ffprobe_data(cls, file_path: str, tool_data: dict):
        intr_data: dict = {}

        video_dto = cls(**intr_data)
        return video_dto
