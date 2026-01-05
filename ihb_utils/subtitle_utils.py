import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def get_subtitle_stream_desc(stream: Dict[str, Any]) -> str:
    return f"Stream {stream["index"]} (Lang: {get_stream_lang(stream)}, Title: {get_stream_tag(stream, 'title') or "N/A"}, Default={stream.get("disposition", {}).get("default") == 1})"


def filter_streams_eng(streams: List) -> Dict[str, Any] | None:
    eng_stream_list = list(filter(lambda stream: get_stream_lang(stream).lower() == "eng", streams))
    logger.debug(f" --> Found {len(eng_stream_list)} english streams")
    return eng_stream_list


def filter_streams_unknown(streams: List) -> Dict[str, Any] | None:
    unk_stream_list = list(filter(lambda stream: get_stream_lang(stream).lower() == "und" or not get_stream_lang(stream), streams))
    logger.debug(f" --> Found {len(unk_stream_list)} unknown language streams")
    return unk_stream_list


def get_subtitle_size_est(stream: Dict[str, Any]) -> int:
    size_est = int(stream.get("nb_frames", "") or get_stream_tag(stream, "NUMBER_OF_FRAMES") or "0")
    logger.debug(f"Stream {stream["index"]} size est: {size_est}")
    return size_est


def get_stream_lang(stream: Dict[str, Any]) -> str:
    stream_lang = get_stream_tag(stream, tag="language") or "und"
    return stream_lang.lower()


def get_stream_tag(stream: Dict[str, Any], tag: str) -> str | None:
    stream_tags = stream.get("tags", {})
    stream_tag = stream_tags.get(tag, "") or stream_tags.get(tag.lower(), "") or stream_tags.get(tag.upper(), "")

    return stream_tag
