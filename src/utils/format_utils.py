"""Parsers for the text resources consumed by MemAgent."""

from __future__ import annotations

import re


PRODUCT_FIELDS = (
    "Action time",
    "Action type",
    "Product name",
    "Price",
    "Product description",
    "Categories",
    "Brand name",
    "Shop name",
    "Attributes",
    "Extra information",
)
VIDEO_FIELDS = (
    "Action time",
    "Action type",
    "Video title",
    "Video description",
    "Staytime",
    "OCR text",
    "ASR text",
    "Product introducted in this video",
    "Price",
    "Product description",
    "Categories",
    "Brand name",
    "Shop name",
)
CANDIDATE_FIELDS = PRODUCT_FIELDS[2:]


def _key(field: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", field.lower()).strip("_")


def _parse(value: str, fields: tuple[str, ...]) -> dict[str, str]:
    field_names = "|".join(re.escape(field) for field in fields)
    marker_pattern = re.compile(
        rf"^(?:<<<(?P<marked>{field_names})>>>|(?P<plain>{field_names}):)\s*$",
        re.MULTILINE,
    )
    matches = list(marker_pattern.finditer(value))
    parsed: dict[str, str] = {}
    for position, match in enumerate(matches):
        field = match.group("marked") or match.group("plain")
        end = matches[position + 1].start() if position + 1 < len(matches) else len(value)
        parsed[_key(field)] = value[match.end() : end].strip() or "None"
    for field in fields:
        parsed.setdefault(_key(field), "None")
    return parsed


def parse_product_text(value: str) -> dict[str, str]:
    return _parse(value, PRODUCT_FIELDS)


def parse_product_text_new(value: str) -> dict[str, str]:
    return _parse(value, PRODUCT_FIELDS)


def parse_video_text(value: str) -> dict[str, str]:
    return _parse(value, VIDEO_FIELDS)


def parse_video_text_new(value: str) -> dict[str, str]:
    return _parse(value, VIDEO_FIELDS)


def parse_candidate_product_text(value: str) -> dict[str, str]:
    return _parse(value, CANDIDATE_FIELDS)


def parse_candidate_product_text_new(value: str) -> dict[str, str]:
    return _parse(value, CANDIDATE_FIELDS)


__all__ = [
    "parse_product_text",
    "parse_product_text_new",
    "parse_video_text",
    "parse_video_text_new",
    "parse_candidate_product_text",
    "parse_candidate_product_text_new",
]
