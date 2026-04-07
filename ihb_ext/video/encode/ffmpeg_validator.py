import logging
from collections.abc import Callable
from enum import Enum, auto
from typing import Any

from ihb_video.types.video_models import Resolution, ValidationResultDTO

from ..info.ffprobe import _get_timecode_data

logger = logging.getLogger(__name__)

VALIDATOR_DICT: {VALIDATION_TYPE, list[Callable]} = {}


class VALIDATION_TYPE(Enum):
    ANY = auto()
    DELTA = auto()
    INVARIANT = auto()
    ANALYSIS = auto()
    BENCHMARK = auto()


def _run_validation(
    old_probe_data: dict[str, Any], new_probe_data: dict[str, Any], test_type: VALIDATION_TYPE = VALIDATION_TYPE.ANY
) -> list[ValidationResultDTO]:
    results_list = []

    for validator in VALIDATOR_DICT[test_type]:
        results_dto = None
        try:
            test_name = str(validator.__name__).replace("_validate_", "")
            logger.info(f"Running {test_name} validation")
            results_dto = validator(old_probe_data, new_probe_data)
            logger.info(f"Results: {str(results_dto)}")
        except Exception as e:
            logger.error(f"Test '{test_name}' failed unexpectedly: {e}", exc_info=True)
            results_dto = ValidationResultDTO(test_name, False, str(e))
        results_list.append(results_dto)

    return results_list


def register_test(test_type: VALIDATION_TYPE):
    def decorator(func):
        VALIDATOR_DICT.setdefault(test_type, []).append(func)
        if test_type != VALIDATION_TYPE.BENCHMARK:
            VALIDATOR_DICT.setdefault(VALIDATION_TYPE.ANY, []).append(func)
        return func

    return decorator


@register_test(VALIDATION_TYPE.DELTA)
def _validate_duration_delta(old_probe_data: dict[str, Any], new_probe_data: dict[str, Any]) -> ValidationResultDTO:
    duration_delta = abs(float(old_probe_data["format_data"]["duration"]) - float(new_probe_data["format_data"]["duration"]))
    result = duration_delta <= 0.1
    return ValidationResultDTO("duration_delta", result, f"Duration delta {duration_delta:.04f} is {"" if result else "UN"}ACCEPTABLE")


@register_test(VALIDATION_TYPE.DELTA)
def _validate_aspect_ratio_delta(old_probe_data: dict[str, Any], new_probe_data: dict[str, Any]) -> ValidationResultDTO:
    old_ar_num = Resolution(old_probe_data["v_streams"][0]["width"], old_probe_data["v_streams"][0]["height"]).get_aspect_ratio_num()
    new_ar_num = Resolution(new_probe_data["v_streams"][0]["width"], new_probe_data["v_streams"][0]["height"]).get_aspect_ratio_num()
    ar_num_delta = abs(old_ar_num - new_ar_num)
    result = ar_num_delta <= 0.02
    return ValidationResultDTO("aspect_ratio_delta", result, f"Aspect Ratio delta {ar_num_delta:.04f} is {"" if result else "UN"}ACCEPTABLE")


@register_test(VALIDATION_TYPE.ANALYSIS)
def _validate_timecode_data(old_probe_data: dict[str, Any], new_probe_data: dict[str, Any]) -> ValidationResultDTO:
    timecode_data = _get_timecode_data(new_probe_data["format_data"]["filename"])
    if not timecode_data:
        return ValidationResultDTO("timecodes", False, "NO timecode data")
    num_freeze = 0
    idx = 1
    len_tdc = len(timecode_data)
    while idx < len_tdc:
        if timecode_data[idx - 1].time_code > timecode_data[idx].time_code + 0.1:
            num_freeze += 1
        idx += 1

    return ValidationResultDTO("timecodes", num_freeze == 0, f"Potential freeze points: {num_freeze} / {idx}")


@register_test(VALIDATION_TYPE.ANALYSIS)
def _validate_stream_integrity(old_probe_data: dict[str, Any], new_probe_data: dict[str, Any]) -> ValidationResultDTO:
    from .ffmpeg import _run_stream_integrity_analysis

    file_path = new_probe_data["format_data"]["filename"]
    result = _run_stream_integrity_analysis(file_path)

    return ValidationResultDTO("stream_integrity", result.returncode == 0, "No errors" if result.returncode == 0 else result.stderr)


@register_test(VALIDATION_TYPE.INVARIANT)
def _validate_color_code(old_probe_data: dict[str, Any], new_probe_data: dict[str, Any]) -> ValidationResultDTO:
    color_code = new_probe_data["v_streams"][0]["pix_fmt"]
    success = color_code == "yuv420p10le"

    return ValidationResultDTO("color_code", success, f"{"" if success else "IN"}CORRECT color code set: {color_code}")


@register_test(VALIDATION_TYPE.INVARIANT)
def _validate_field_order(old_probe_data: dict[str, Any], new_probe_data: dict[str, Any]) -> ValidationResultDTO:
    field_order = new_probe_data["v_streams"][0]["field_order"]
    success = field_order == "progressive"

    return ValidationResultDTO("field_order", success, f"{"" if success else "IN"}CORRECT scan type set: {field_order}")


def test():
    pass


if __name__ == "__main__":
    test()
