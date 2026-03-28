import json
import logging
from dataclasses import asdict, dataclass, field, fields
from pathlib import PurePath
from sqlite3 import Row
from typing import Any

from humanfriendly import format_size

from ihb_common.utils.gen_utils import format_time

logger = logging.getLogger(__name__)
METADATA_VERSION = 1.0


@dataclass
class File_DTO:
    path: str
    hash: str
    size: int
    duration: float
    md_version: float = METADATA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_pretty_str(self):
        ret_val = f"{self.path} || {self.hash} || {format_size(self.size)} || {format_time(self.duration)}"
        return ret_val

    @classmethod
    def from_pym_data(cls, file_data: dict[str, Any], hash: str):
        format_data: dict[str, Any] = file_data["format_data"]
        path = PurePath(format_data["complete_name"]).as_posix().lower()
        size = int(format_data["file_size"])
        duration = float(format_data.get("duration", 0))

        metadata = _generate_pym_db_metadata(file_data)

        return cls(path=path, hash=hash, size=size, duration=duration, metadata=metadata)

    @classmethod
    def from_probe_data(cls, file_data: dict[str, Any], hash: str):
        format_data: dict[str, Any] = file_data["format_data"]

        path = PurePath(format_data["filename"]).as_posix().lower()
        size = int(format_data["size"])
        duration = float(format_data.get("duration", 0))

        metadata = _generate_db_metadata(file_data)

        return cls(path=path, hash=hash, size=size, duration=duration, metadata=metadata)

    @classmethod
    def from_db_record(cls, record: Row):
        class_fields = {field.name for field in fields(cls)}
        filtered_fields = {key: value for key, value in dict(record).items() if key in class_fields}
        filtered_fields["path"] = PurePath(filtered_fields["path"]).as_posix().lower()
        file_dto: File_DTO = cls(**filtered_fields)

        metadata = json.loads(record["metadata"]) if record["metadata"] else {}
        file_dto.metadata = metadata

        return file_dto

    def to_db_params(self) -> dict[str, Any]:
        db_params = asdict(self)
        db_params["path"] = PurePath(self.path).as_posix().lower()
        db_params["metadata"] = json.dumps(self.metadata) if self.metadata else None

        return db_params


def _generate_pym_db_metadata(file_data: dict[str, Any]) -> dict[str, Any]:
    metadata = {}

    format_data = file_data["format_data"]

    video_data = file_data["v_streams"][0]
    metadata["video_codec"] = video_data.get("format", "unknown")
    metadata["resolution"] = f"{video_data.get("width", 0)}x{video_data.get("height", 0)}"
    metadata["frame_rate"] = video_data.get("frame_rate", "0")

    if file_data["a_count"] > 0:
        audio_data = file_data["a_streams"][0]
        metadata["audio_codec"] = audio_data.get("format", "unknown")
        metadata["bit_rate"] = audio_data.get("sampling_rate", 0)

    return metadata


def _generate_db_metadata(file_data: dict[str, Any]) -> dict[str, Any]:
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
