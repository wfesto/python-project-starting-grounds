import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CliArgument:
    flag: str
    name: str
    help: str = None
    type: type = None
    action: str = None
    nargs: str = None

    def get_args(self) -> tuple[str, str]:
        return f"-{self.flag}", f"--{self.name}"

    def get_kwargs(self) -> dict[str, Any]:
        kwargs = {}

        for key, value in asdict(self).items():
            if value:
                kwargs[key] = value

        kwargs.pop("flag")
        kwargs.pop("name")

        return kwargs


class WorkflowManager(Protocol):
    COMMAND_MAP: dict[str, Callable] = {}
    FLAG_MAP: dict[str, tuple[CliArgument, ...]] = {}
    CLI_HELP: str

    def get_actions() -> list[str]: ...
    def dispatch(*args: Any, **kwargs: Any) -> Any: ...


class BaseWorkflowManager:
    @classmethod
    def get_actions(cls) -> list[str]:
        return cls.COMMAND_MAP.keys()

    @classmethod
    def dispatch(cls, *args, **kwargs) -> Any:
        action = kwargs.pop("action")
        logger.verbose(kwargs)
        if method := cls.COMMAND_MAP.get(action):
            try:
                logger.info(f"Executing {action}")
                args_dict = {k: v for k, v in kwargs.items() if v is not None}
                return method(*args, **args_dict)
            except Exception as e:
                logger.error(f"Error executing {action}: {str(e)}", exc_info=True)
        else:
            logger.error(f"Undefined action: {action}")

    @classmethod
    def register_command(cls, keyword: str, *cli_args: CliArgument):
        def decorator(func: Callable):
            cls.COMMAND_MAP[keyword] = func
            if cli_args:
                cls.FLAG_MAP[keyword] = cli_args
            return func

        return decorator
