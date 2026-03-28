from enum import Enum, auto


class StreamType(Enum):
    VIDEO = auto()
    AUDIO = auto()
    SUBTITLE = auto()
    UNKNOWN = 9
