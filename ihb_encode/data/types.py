import json
import os
from dataclasses import asdict, dataclass, field, fields
from enum import Enum, IntEnum, auto
from pathlib import PurePath
from sqlite3 import Row
from typing import Any

from humanfriendly import format_size

from ihb_common.utils.gen_utils import format_time


@dataclass(frozen=True)
class EncodingProfile:
    name: str
    resolution: str
    fixed_dim: int
    scaled_dim: int
    crf: int
    encoder_preset: str
    params_x265: list[str]
    is_source: bool


class Profile(Enum):
    P1080 = "1080p"
    P720 = "720p"
    P480 = "480p"
    SOURCE = "source"


PROFILES = {
    Profile.P1080: EncodingProfile("1080p", "1080p", 1080, 1920, 22, "slow", [], False),
    Profile.P720: EncodingProfile("720p", "720p", 720, 1280, 23, "slow", [], False),
    Profile.P480: EncodingProfile("480p", "480p", 480, 854, 24, "slow", [], False),
    Profile.SOURCE: EncodingProfile("source", "Source Res", 0, 0, 26, "slow", [], True),
}


def get_profile(input: str | int) -> EncodingProfile | None:
    input = input.lower() if isinstance(input, str) else input
    if ((isinstance(input, str) and input.isnumeric()) or isinstance(input, int)) and int(input) in range(len(Profile)):
        return PROFILES[list(Profile)[int(input)]]
    elif input in Profile:
        return PROFILES[Profile(input)]
    else:
        return PROFILES.get(getattr(Profile, str(input).upper(), None), None)


class Job_Status(IntEnum):
    INIT = auto()
    PENDING = auto()
    IND_JOB = auto()
    WORKING = auto()
    REVIEW = auto()
    COMPLETE = auto()
    ERROR = auto()
    MAN_APPR = auto()
    DELETED = auto()
    CANCELLED = auto()
    POST_PROC = auto()
    UNKNOWN = 99

    def to_sql_params(self, language: str) -> dict[str, Any]:
        sql_params = {}
        sql_params["status"] = self.value
        sql_params["status_name"] = self.name
        sql_params["language"] = language
        return sql_params


@dataclass
class Encoding_Job_DTO:
    job_id: int
    input: str
    output: str
    profile: Profile
    duration: int
    size_in: int
    size_out: int = None
    status: Job_Status = None
    notes: dict[str, Any] = field(default_factory=dict)

    def to_pretty_string(self):
        return f"{format_time(self.duration)} \t {format_size(self.size_in)}\t{self.profile.name}\t{self.job_id}\t{os.path.basename(self.input)}"

    def to_sql_params(self):
        db_params = asdict(self)

        db_params["input"] = PurePath(self.input).as_posix()
        db_params["output"] = PurePath(self.output).as_posix() if self.output else None

        if x_profile := db_params.pop("profile", None):
            db_params["profile"] = x_profile["name"].lower()

        if x_status := db_params.pop("status", None):
            db_params["status"] = x_status.value

        return db_params

    @classmethod
    def from_sql_row(cls, row: Row):
        class_fields = {field.name for field in fields(cls)}
        filtered_fields = {key: value for key, value in dict(row).items() if key in class_fields}
        job_dto: Encoding_Job_DTO = cls(**filtered_fields)

        job_dto.input = PurePath(filtered_fields["input"]).as_posix()
        job_dto.output = PurePath(filtered_fields["output"]).as_posix() if "output" in filtered_fields else None

        job_dto.profile = get_profile(filtered_fields["profile"])
        job_dto.status = Job_Status(filtered_fields["status"])

        if job_dto.notes:
            job_dto.notes = json.loads(job_dto.notes)
        else:
            job_dto.notes = {}

        return job_dto
