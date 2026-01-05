import json
import logging
from sqlite3 import Row
from typing import Any, Dict

from humanfriendly import format_size

from ihb_utils.gen_utils import format_time

logger = logging.getLogger(__name__)


METADATA_VERSION = 1.0


class File_DTO:
    path: str
    hash: str
    size: int
    duration: float
    md_version: float
    metadata: Dict[str, Any]

    def __init__(self, path: str, hash: str, size: int, duration: float, metadata: Dict[str, Any], md_version: float = METADATA_VERSION):
        self.path = path
        self.hash = hash
        self.size = size
        self.duration = duration
        self.md_version = md_version
        self.metadata = metadata

    def __str__(self):
        ret_val = f"{self.path} || {self.hash} || {format_size(self.size)} || {format_time(self.duration)}"
        return ret_val

    def __repr__(self):
        str_val = self.__str__()
        ret_val = f"{str_val} || v{self.md_version} {repr(self.metadata)}"
        return ret_val

    @classmethod
    def from_probe_data(cls, file_data: Dict[str, Any], hash: str):
        format_data = file_data["format_data"]

        path = format_data["filename"]
        size = int(format_data["size"])
        duration = float(format_data.get("duration", 0))

        metadata = _generate_db_metadata(file_data)

        return cls(path=path, hash=hash, size=size, duration=duration, metadata=metadata)

    @classmethod
    def from_db_record(cls, record: Row):
        path = record["path"]
        hash = record["hash"]
        size = record["size"]
        duration = record["duration"]
        md_version = record["md_Version"]
        metadata = json.loads(record["metadata"])

        return cls(path=path, hash=hash, size=size, duration=duration, metadata=metadata, md_version=md_version)

    def to_db_params(self) -> Dict[str, Any]:
        db_params = {
            "path": self.path,
            "hash": self.hash,
            "size": self.size,
            "duration": self.duration,
            "md_version": self.md_version,
            "metadata": json.dumps(self.metadata),
        }

        return db_params


def _generate_db_metadata(file_data: Dict[str, Any]) -> Dict[str, Any]:
    metadata = {}

    format_data = file_data["format_data"]

    video_data = file_data["v_streams"][0]
    metadata["video_codec"] = video_data.get("codec_name", "unknown")
    metadata["resolution"] = f"{video_data.get("width", 0)}x{video_data.get("height", 0)}"
    metadata["frame_rate"] = video_data.get("avg_frame_rate", "0")

    if file_data["a_count"] > 0:
        audio_data = file_data["a_streams"][0]
        metadata["audio_codec"] = audio_data.get("codec_name", "unknown")
        metadata["bit_rate"] = audio_data.get("bit_rate", 0)

    return metadata
