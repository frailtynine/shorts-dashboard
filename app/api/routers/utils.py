"""Helpers for preparing dashboard-friendly values and summaries."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from statistics import mean

RU_MONTHS = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def format_short_num(value: float) -> str:
    """Format large counts into compact Russian labels."""
    number = float(value)
    abs_num = abs(number)

    if abs_num >= 1_000_000_000:
        return _format_compact(number / 1_000_000_000, " млрд")
    if abs_num >= 1_000_000:
        return _format_compact(number / 1_000_000, " млн")
    if abs_num >= 1_000:
        return _format_compact(number / 1_000, " тыс")

    return str(round(number))


def format_date_ru(value: date) -> str:
    """Format a date in the dashboard's Russian locale style."""
    month_name = RU_MONTHS[value.month]
    return f"{value.day} {month_name} {value.year}"


def get_week_start_date(value: date) -> date:
    """Return Monday for the week containing the provided date."""
    return value - timedelta(days=value.weekday())


def get_week_end_date(value: date) -> date:
    """Return Sunday for the week containing the provided date."""
    return get_week_start_date(value) + timedelta(days=6)


def format_week_label_ru(week_end: date) -> str:
    """Build a readable label for a week using its end date."""
    week_start = get_week_start_date(week_end)
    return f"{format_date_ru(week_start)} - {format_date_ru(week_end)}"


def parse_week(value: str | None) -> date | None:
    """Parse an ISO date string used by the week query parameter."""
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def build_channel_options(
    channel_rows: Iterable[tuple[str, str]],
    configured_channels: list[str],
) -> list[dict[str, str]]:
    """Build channel options from configured channels only."""
    titles_by_id: dict[str, str] = {}
    for channel_id, channel_title in channel_rows:
        titles_by_id[channel_id] = channel_title or channel_id

    ordered_ids: list[str] = []
    for channel_id in configured_channels:
        titles_by_id.setdefault(channel_id, channel_id)
        if channel_id not in ordered_ids:
            ordered_ids.append(channel_id)

    return [
        {
            "channel_id": channel_id,
            "channel_title": titles_by_id[channel_id],
        }
        for channel_id in ordered_ids
    ]


def resolve_selected_channel(
    requested_channel: str | None,
    channel_options: list[dict[str, str]],
    configured_channels: list[str],
) -> str | None:
    """Resolve the selected channel with settings-based defaults."""
    available_ids = {item["channel_id"] for item in channel_options}

    if requested_channel and requested_channel in available_ids:
        return requested_channel
    if configured_channels:
        return configured_channels[0]
    if channel_options:
        return channel_options[0]["channel_id"]
    return None


def build_available_weeks(
    published_values: Iterable[datetime | None],
) -> list[dict[str, str]]:
    """Build selectable week options ordered from latest to oldest."""
    week_ends = sorted(
        {
            get_week_end_date(published_at.date())
            for published_at in published_values
            if published_at is not None
        },
        reverse=True,
    )
    return [
        {
            "key": week_end.isoformat(),
            "label": format_week_label_ru(week_end),
        }
        for week_end in week_ends
    ]


def resolve_selected_week(
    requested_week: str | None,
    available_weeks: list[dict[str, str]],
) -> str | None:
    """Resolve the selected week key with latest-week fallback."""
    available_keys = {item["key"] for item in available_weeks}
    if requested_week and requested_week in available_keys:
        return requested_week
    if available_weeks:
        return available_weeks[0]["key"]
    return None


def serialize_dashboard_rows(rows: Iterable[object]) -> list[dict[str, object]]:
    """Convert SQLAlchemy row objects into dashboard dictionaries."""
    return [
        {
            "video_id": row.video_id,
            "channel_id": row.channel_id,
            "channel_title": row.channel_title,
            "title": row.title,
            "duration_seconds": int(row.duration_seconds or 0),
            "view_count": int(row.view_count or 0),
            "like_count": int(row.like_count or 0),
            "comment_count": int(row.comment_count or 0),
            "published_at": row.published_at,
            "theme_name": row.theme_name or "Без темы",
        }
        for row in rows
    ]


def build_weekly_stats(
    shorts: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Aggregate dashboard rows into per-week summary cards."""
    weekly: dict[str, dict[str, object]] = {}

    for item in shorts:
        published_at = item["published_at"]
        if not isinstance(published_at, datetime):
            continue

        week_start = get_week_start_date(published_at.date())
        week_key = week_start.isoformat()
        bucket = weekly.setdefault(
            week_key,
            {
                "week_start": week_key,
                "week_end": get_week_end_date(published_at.date()).isoformat(),
                "total_shorts": 0,
                "total_views": 0,
                "avg_duration": 0,
                "avg_views": 0,
                "themes": {},
                "durations": [],
                "views": [],
            },
        )

        theme_name = str(item["theme_name"])
        duration = int(item["duration_seconds"])
        views = int(item["view_count"])

        bucket["total_shorts"] += 1
        bucket["total_views"] += views
        bucket["durations"].append(duration)
        bucket["views"].append(views)

        themes = bucket["themes"]
        if theme_name not in themes:
            themes[theme_name] = {
                "count": 0,
                "total_views": 0,
                "avg_views": 0,
            }
        themes[theme_name]["count"] += 1
        themes[theme_name]["total_views"] += views

    weekly_stats: list[dict[str, object]] = []
    for _, value in sorted(weekly.items(), key=lambda item: item[0], reverse=True):
        durations = value.pop("durations")
        views = value.pop("views")
        week_end = parse_week(str(value["week_end"]))
        value["week_label"] = format_week_label_ru(
            week_end or datetime.now(UTC).date()
        )
        value["avg_duration"] = round(mean(durations), 1) if durations else 0
        value["avg_views"] = round(mean(views), 1) if views else 0

        prepared_themes = []
        for name, stats in value["themes"].items():
            theme_avg = 0
            if stats["count"]:
                theme_avg = stats["total_views"] / stats["count"]
            prepared_themes.append(
                {
                    "name": name,
                    "count": stats["count"],
                    "total_views": stats["total_views"],
                    "avg_views": round(theme_avg, 1),
                }
            )

        value["themes"] = sorted(
            prepared_themes,
            key=lambda item: item["avg_views"],
            reverse=True,
        )
        weekly_stats.append(value)

    return weekly_stats


def build_chart_data(weekly_stats: list[dict[str, object]]) -> dict[str, list]:
    """Build chart.js payloads from the already filtered weekly stats."""
    chart_weeks = list(reversed(weekly_stats))
    theme_rows = weekly_stats[0]["themes"] if weekly_stats else []

    return {
        "labels": [item["week_label"] for item in chart_weeks],
        "weekly_views": [item["total_views"] for item in chart_weeks],
        "weekly_counts": [item["total_shorts"] for item in chart_weeks],
        "weekly_avg_duration": [
            item["avg_duration"] for item in chart_weeks
        ],
        "theme_labels": [item["name"] for item in theme_rows],
        "theme_values": [item["avg_views"] for item in theme_rows],
    }


def build_shorts_table(shorts: list[dict[str, object]]) -> list[dict[str, object]]:
    """Build sorted table rows for the currently selected payload."""
    shorts_table: list[dict[str, object]] = []
    sorted_pool = sorted(
        shorts,
        key=lambda item: int(item["view_count"]),
        reverse=True,
    )

    for item in sorted_pool:
        published_at = item["published_at"]
        published_label = ""
        published_sort = ""
        if isinstance(published_at, datetime):
            published_label = format_date_ru(published_at.date())
            published_sort = published_at.isoformat()

        shorts_table.append(
            {
                "video_id": item["video_id"],
                "title": item["title"],
                "theme_name": item["theme_name"],
                "duration_seconds": item["duration_seconds"],
                "view_count": item["view_count"],
                "like_count": item["like_count"],
                "comment_count": item["comment_count"],
                "published_label": published_label,
                "published_sort": published_sort,
            }
        )

    return shorts_table


def _format_compact(value: float, suffix: str) -> str:
    """Format a number with one decimal and a Russian suffix."""
    text = f"{value:.1f}".replace(".", ",")
    text = text.rstrip("0").rstrip(",")
    return text + suffix
