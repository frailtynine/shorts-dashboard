from collections.abc import Iterable, Iterator, Mapping
import re
from typing import TypeVar


T = TypeVar("T")


_ISO_DURATION_RE = re.compile(
    r"^P"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$"
)


def chunked(items: Iterable[T], size: int) -> Iterator[list[T]]:
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []

    if batch:
        yield batch


def parse_iso8601_duration(value: str) -> int:
    match = _ISO_DURATION_RE.match(value)
    if match is None:
        return 0

    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return (((days * 24) + hours) * 60 + minutes) * 60 + seconds


def pick_thumbnail_url(thumbnails: Mapping[str, object]) -> str:
    for key in ("maxres", "standard", "high", "medium", "default"):
        candidate = thumbnails.get(key)
        if not isinstance(candidate, Mapping):
            continue
        url = candidate.get("url")
        if isinstance(url, str) and url:
            return url
    return ""
