import logging
from collections.abc import Callable

from ihb_common.utils.file_utils import recycle_file
from ihb_video.manager.video_manager import play_video_file

logger = logging.getLogger(__name__)

COMMAND_MAP: dict[str, Callable] = {
    "v": play_video_file,
    "d": recycle_file,
}


def prompt_duplicate_action(file_list: list[str]) -> bool:
    for idx, file in enumerate(file_list, 1):
        print(f"[{idx}] {file}")
    print("[v]x [V]LC file")
    print("[d]x [D]elete file")
    print("[i]gnore match")
    print("[s]kip files")
    print("[q]uit")
    print()

    while len(file_list) > 1:
        user_actions = list(input("Choose options:  ").lower())
        while user_actions:
            action = user_actions.pop(0)
            if action == "s":
                return True
            elif action == "q":
                return False
            elif action == "i":
                break
            elif action in COMMAND_MAP.keys():
                if user_actions and str.isdigit(user_actions[0]):
                    file_idx = int(user_actions.pop(0)) - 1
                    if file_idx < 0 or file_idx >= len(file_list):
                        print("Invalid file choice.")
                        continue
                    file_choice = file_list[file_idx]
                    COMMAND_MAP[action](file_choice)
                    if action == "d":
                        file_list.remove(file_choice)
                    continue

            print("Invalid choice")

    return True
