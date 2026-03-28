import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class DbManager(Protocol):
    pass


class BaseDbManager:
    pass
