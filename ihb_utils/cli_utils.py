from dataclasses import asdict, dataclass
from typing import Any, Protocol


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


class Workflow_Manager(Protocol):
    FLAG_MAP: dict[str, tuple[CliArgument, ...]]
    CLI_HELP: str

    def get_actions() -> list[str]: ...
    def dispatch(*args: Any, **kwargs: Any) -> None: ...
