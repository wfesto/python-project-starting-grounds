import logging

from ihb_common.utils.gen_utils import generate_aligned_table
from ihb_components.tui.types import *

logger = logging.getLogger(__name__)


def show_multi_file_options(
    header_info: list[str] = [],
    file_list: list[FileMenuDataDTO] = [],
    file_data_headers: list[str] = [],
    file_actions: list[MenuChoiceDTO] = [],
    rotate_file_data: bool = False,
    menu_actions: list[MenuChoiceDTO] = [],
    prompt_string: str = "Enter an option and press ENTER: ",
) -> str:
    menu_commands = set(dto.command for dto in menu_actions)
    file_commands = {dto.command: dto for dto in file_actions}

    print("-" * 25)
    for header in header_info or []:
        print(header)
    print("-" * 25)

    for idx, file_dto in enumerate(file_list):
        print(f"[{idx +1}] {file_dto.file_path}")

    data_list = [file_data_headers]
    for file_dto in file_list:
        data_list.append(file_dto.file_data)

    table_data = generate_aligned_table(*data_list, rotate=rotate_file_data)
    for data in table_data:
        print(data)

    print()

    for file_action in file_actions or []:
        print(f"{file_action.command}x: {file_action.display}")
    for menu_action in menu_actions or []:
        print(f"{menu_action.command}: {menu_action.display}")

    print()

    while True:
        user_input = None
        file_idx = None
        chosen_file = None

        user_input = list(input(prompt_string + " ").strip().lower())
        menu_choice = None
        while user_input:
            command = user_input.pop(0)
            if command in menu_commands:
                menu_choice = command
            elif command in file_commands.keys():
                file_action = file_commands[command]
                if user_input and user_input[0].isdigit():
                    file_idx = int(user_input.pop(0)) - 1
                    if 0 <= file_idx < len(file_list):
                        chosen_file = file_list[file_idx]
                    else:
                        logger.warning(f"{file_idx} not in list range")
                        continue
                if not chosen_file and file_action.get_default_file:
                    chosen_file = file_action.get_default_file(file_list, file_action)
                if not chosen_file:
                    logger.warning(f"No file chosen for action {command}, skipping command.")
                else:
                    file_action.file_action(chosen_file.file_path)
            else:
                logger.warning(f"Invalid selection: {command}, ignoring")

        if menu_choice:
            return menu_choice
