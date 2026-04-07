from enum import Enum, auto


class StreamType(Enum):
    VIDEO = auto()
    AUDIO = auto()
    SUBTITLE = auto()
    UNKNOWN = 9

    def get_stream_key(self) -> str:
        return self.name[0].lower()
