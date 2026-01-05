import logging
from typing import Any, Dict, List

from ihb_ext.ffprobe import _get_timecode_data
from ihb_utils.video_models import Resolution, Validation_Results_DTO

logger = logging.getLogger(__name__)

VALIDATOR_DICT = {}


def _run_validation(old_probe_data: Dict[str, Any], new_probe_data: Dict[str, Any]) -> List[Validation_Results_DTO]:
    results_list = []

    for test_name, validator in VALIDATOR_DICT.items():
        results_dto = None
        try:
            logger.verbose(f"Running {test_name} validation")
            results_dto = validator(old_probe_data, new_probe_data)
        except Exception as e:
            logger.error(f"Test '{test_name}' failed unexpectedly: {e}", exc_info=True)
            results_dto = Validation_Results_DTO(test_name, False, str(e))
        results_list.append(results_dto)

    return results_list


def register_test(test_name: str):
    def decorator(func):
        VALIDATOR_DICT[test_name] = func
        return func

    return decorator


@register_test("duration_delta")
def _validate_duration_delta(old_probe_data: Dict[str, Any], new_probe_data: Dict[str, Any]) -> Validation_Results_DTO:
    duration_delta = abs(float(old_probe_data["format_data"]["duration"]) - float(new_probe_data["format_data"]["duration"]))
    result = duration_delta <= 0.05
    return Validation_Results_DTO("duration_delta", result, f"Duration delta {duration_delta:.04f} is {"" if result else "UN"}ACCEPTABLE")


@register_test("aspect_ratio_delta")
def _validate_aspect_ratio_delta(old_probe_data: Dict[str, Any], new_probe_data: Dict[str, Any]) -> Validation_Results_DTO:
    old_ar_num = Resolution(old_probe_data["v_streams"][0]["width"], old_probe_data["v_streams"][0]["height"]).get_aspect_ratio_num()
    new_ar_num = Resolution(new_probe_data["v_streams"][0]["width"], new_probe_data["v_streams"][0]["height"]).get_aspect_ratio_num()
    ar_num_delta = abs(old_ar_num - new_ar_num)
    result = ar_num_delta <= 0.005
    return Validation_Results_DTO("duration_delta", result, f"Aspect Ratio delta {ar_num_delta:.04f} is {"" if result else "UN"}ACCEPTABLE")


@register_test("timecodes")
def _validate_timecode_data(old_probe_data: Dict[str, Any], new_probe_data: Dict[str, Any]) -> Validation_Results_DTO:
    timecode_data = _get_timecode_data(new_probe_data["format_data"]["filename"])
    if not timecode_data:
        return Validation_Results_DTO("timecodes", False, "NO timecode data")
    num_freeze = 0
    idx = 1
    len_tdc = len(timecode_data)
    while idx < len_tdc:
        if timecode_data[idx - 1].time_code > timecode_data[idx].time_code + 0.1:
            num_freeze += 1
        idx += 1

    return Validation_Results_DTO("timecodes", num_freeze == 0, f"Potential freeze points: {num_freeze} / {idx}")


@register_test("color_code")
def _validate_color_code(old_probe_data: Dict[str, Any], new_probe_data: Dict[str, Any]) -> Validation_Results_DTO:
    color_code = new_probe_data["v_streams"][0]["pix_fmt"]
    success = color_code == "yuv420p10le"

    return Validation_Results_DTO("color_code", success, f"{"" if success else "IN"}CORRECT color code set: {color_code}")


@register_test("field_order")
def _validate_field_order(old_probe_data: Dict[str, Any], new_probe_data: Dict[str, Any]) -> Validation_Results_DTO:
    field_order = new_probe_data["v_streams"][0]["field_order"]
    success = field_order == "progressive"

    return Validation_Results_DTO("field_order", success, f"{"" if success else "IN"}CORRECT scan type set: {field_order}")


def test():
    pass


if __name__ == "__main__":
    test()
