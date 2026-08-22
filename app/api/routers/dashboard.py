from datetime import date, datetime, timedelta
from statistics import mean

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RetrievedShort, Theme
from app.db.session import get_db_session


router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


def _short_num(value: float | int) -> str:
    number = float(value)
    abs_num = abs(number)

    if abs_num >= 1_000_000_000:
        compact = number / 1_000_000_000
        text = f"{compact:.1f}".replace(".", ",")
        text = text.rstrip("0").rstrip(",")
        return text + " млрд"
    if abs_num >= 1_000_000:
        compact = number / 1_000_000
        text = f"{compact:.1f}".replace(".", ",")
        text = text.rstrip("0").rstrip(",")
        return text + " млн"
    if abs_num >= 1_000:
        compact = number / 1_000
        text = f"{compact:.1f}".replace(".", ",")
        text = text.rstrip("0").rstrip(",")
        return text + " тыс"

    return str(int(round(number)))


templates.env.filters["short_num"] = _short_num


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


@router.get("", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    channel: str | None = Query(default=None),
    db: Session = Depends(get_db_session),
) -> HTMLResponse:
    raw_rows = db.execute(
        select(
            RetrievedShort.video_id,
            RetrievedShort.channel_id,
            RetrievedShort.channel_title,
            RetrievedShort.title,
            RetrievedShort.duration_seconds,
            RetrievedShort.view_count,
            RetrievedShort.like_count,
            RetrievedShort.comment_count,
            RetrievedShort.published_at,
            Theme.name.label("theme_name"),
        )
        .outerjoin(Theme, Theme.id == RetrievedShort.theme_id)
        .where((Theme.name.is_(None)) | (Theme.name != "Не обработано"))
        .order_by(RetrievedShort.published_at.desc())
    ).all()

    all_shorts = []
    for row in raw_rows:
        all_shorts.append(
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
        )

    channels_map: dict[str, str] = {}
    for item in all_shorts:
        channels_map[item["channel_id"]] = item["channel_title"]

    channel_options = [
        {
            "channel_id": channel_id,
            "channel_title": title,
        }
        for channel_id, title in sorted(
            channels_map.items(),
            key=lambda item: item[1].lower(),
        )
    ]

    selected_channel = channel
    if selected_channel and selected_channel not in channels_map:
        selected_channel = None

    if not selected_channel and channel_options:
        selected_channel = channel_options[0]["channel_id"]

    shorts_pool = all_shorts
    if selected_channel:
        shorts_pool = [
            item for item in all_shorts
            if item["channel_id"] == selected_channel
        ]

    weekly: dict[str, dict] = {}
    for item in shorts_pool:
        published_at = item["published_at"]
        if not published_at:
            continue
        week_start = _week_start_date(published_at.date())
        week_key = week_start.strftime("%Y-%m-%d")
        if week_key not in weekly:
            weekly[week_key] = {
                "week_start": week_key,
                "total_shorts": 0,
                "total_views": 0,
                "avg_duration": 0,
                "avg_views": 0,
                "themes": {},
                "durations": [],
                "views": [],
            }

        bucket = weekly[week_key]
        theme_name = item["theme_name"]
        duration = item["duration_seconds"]
        views = item["view_count"]

        bucket["total_shorts"] += 1
        bucket["total_views"] += views
        bucket["durations"].append(duration)
        bucket["views"].append(views)
        if theme_name not in bucket["themes"]:
            bucket["themes"][theme_name] = {
                "count": 0,
                "total_views": 0,
                "avg_views": 0,
            }
        bucket["themes"][theme_name]["count"] += 1
        bucket["themes"][theme_name]["total_views"] += views

    weekly_stats = []
    theme_totals: dict[str, dict[str, float]] = {}
    available_weeks: list[dict[str, str]] = []
    sorted_weeks = sorted(
        weekly.items(),
        key=lambda item: item[0],
        reverse=True,
    )
    for _, value in sorted_weeks:
        value["week_label"] = _week_label_ru(value["week_start"])
        available_weeks.append(
            {"key": value["week_start"], "label": value["week_label"]}
        )
        durations = value.pop("durations")
        views = value.pop("views")
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

            if name not in theme_totals:
                theme_totals[name] = {"count": 0, "total_views": 0}
            theme_totals[name]["count"] += stats["count"]
            theme_totals[name]["total_views"] += stats["total_views"]

        sorted_themes = sorted(
            prepared_themes,
            key=lambda item: item["avg_views"],
            reverse=True,
        )
        value["themes"] = [
            {
                "name": item["name"],
                "count": item["count"],
                "total_views": item["total_views"],
                "avg_views": item["avg_views"],
            }
            for item in sorted_themes
        ]
        weekly_stats.append(value)

    all_time_theme_avg = []
    for theme_name, totals in theme_totals.items():
        avg_val = 0
        if totals["count"]:
            avg_val = totals["total_views"] / totals["count"]
        all_time_theme_avg.append({"name": theme_name, "avg_views": avg_val})

    all_time_theme_avg = sorted(
        all_time_theme_avg,
        key=lambda item: item["avg_views"],
        reverse=True,
    )

    chart_weeks = list(reversed(weekly_stats))
    chart_labels = [
        _week_label_ru(item["week_start"]) for item in chart_weeks
    ]
    chart_data = {
        "labels": chart_labels,
        "weekly_views": [item["total_views"] for item in chart_weeks],
        "weekly_counts": [item["total_shorts"] for item in chart_weeks],
        "weekly_avg_duration": [
            item["avg_duration"] for item in chart_weeks
        ],
        "theme_labels": [item["name"] for item in all_time_theme_avg],
        "theme_values": [item["avg_views"] for item in all_time_theme_avg],
    }
    shorts_table = []
    sorted_pool = sorted(
        shorts_pool,
        key=lambda item: item["view_count"],
        reverse=True,
    )
    for item in sorted_pool:
        published_at = item["published_at"]
        published_label = ""
        published_sort = ""
        if published_at:
            published_label = _date_label_ru(published_at.date())
            published_sort = published_at.isoformat()
            week_start = _week_start_date(published_at.date())
            week_key = week_start.strftime("%Y-%m-%d")
        else:
            week_key = ""

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
                "week_key": week_key,
            }
        )

    context = {
        "request": request,
        "generated_at": _date_label_ru(date.today()),
        "weekly_stats": weekly_stats,
        "available_weeks": available_weeks,
        "default_week_key": (
            available_weeks[0]["key"] if available_weeks else "all"
        ),
        "channel_options": channel_options,
        "selected_channel": selected_channel or "",
        "chart_data": chart_data,
        "shorts_table": shorts_table,
    }
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=context,
    )


def _week_label_ru(week_start: str) -> str:
    start_dt = datetime.strptime(week_start, "%Y-%m-%d").date()
    end_dt = start_dt + timedelta(days=6)
    return (
        f"{_date_label_ru(start_dt)}"
        f" - {_date_label_ru(end_dt)}"
    )


def _date_label_ru(value: date) -> str:
    month_name = RU_MONTHS[value.month]
    return f"{value.day} {month_name} {value.year}"


def _week_start_date(value: date) -> date:
    return value - timedelta(days=value.weekday())
