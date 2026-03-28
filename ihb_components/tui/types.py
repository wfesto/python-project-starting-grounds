import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ihb_common.utils.file_utils import recycle_file
from ihb_video.manager import video_manager

logger = logging.getLogger(__name__)


@dataclass
class FileMenuDataDTO:
    file_name: str
    file_path: str
    file_data: list[str] = field(default_factory=list)
    file_extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class MenuChoiceDTO:
    display: str
    command: str
    file_action: Callable = None
    get_default_file: Callable = None


QUIT = MenuChoiceDTO("[q]uit application", "q")
SKIP = MenuChoiceDTO("[s]kip", "s")

DELETE_FILE = MenuChoiceDTO("[d]elete file", "d", recycle_file)
PLAY_VIDEO_FILE = MenuChoiceDTO("play file in [v]lc", "v", video_manager.play_video_file)
