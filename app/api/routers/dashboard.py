from datetime import UTC, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routers.utils import (
    build_available_weeks,
    build_channel_options,
    build_chart_data,
    build_shorts_table,
    build_weekly_stats,
    format_date_ru,
    format_short_num,
    parse_week,
    resolve_selected_channel,
    resolve_selected_week,
    serialize_dashboard_rows,
)
from app.core.config import get_settings
from app.db.models import RetrievedShort, Theme
from app.db.session import get_db_session

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["short_num"] = format_short_num

DBSession = Annotated[Session, Depends(get_db_session)]


@router.get("/", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    channel: str | None = Query(default=None),
    week: str | None = Query(default=None),
    db: DBSession = None,
) -> HTMLResponse:
    """Render a dashboard payload for one channel and one selected week."""
    settings = get_settings()
    channel_rows = db.execute(
        select(
            RetrievedShort.channel_id,
            RetrievedShort.channel_title,
        )
        .distinct()
        .order_by(RetrievedShort.channel_title.asc())
    ).all()
    channel_options = build_channel_options(channel_rows, settings.sync_channels)
    selected_channel = resolve_selected_channel(
        channel,
        channel_options,
        settings.sync_channels,
    )

    available_weeks: list[dict[str, str]] = []
    selected_week = None
    selected_week_label = ""
    shorts: list[dict[str, object]] = []

    if selected_channel:
        published_values = db.scalars(
            select(RetrievedShort.published_at)
            .outerjoin(Theme, Theme.id == RetrievedShort.theme_id)
            .where(RetrievedShort.channel_id == selected_channel)
            .where((Theme.name.is_(None)) | (Theme.name != "Не обработано"))
            .order_by(RetrievedShort.published_at.desc())
        ).all()
        available_weeks = build_available_weeks(published_values)
        selected_week = resolve_selected_week(week, available_weeks)

    selected_week_date = parse_week(selected_week)
    if selected_week_date is not None and selected_channel is not None:
        selected_week_label = next(
            (
                item["label"]
                for item in available_weeks
                if item["key"] == selected_week
            ),
            "",
        )
        week_start = selected_week_date - timedelta(days=6)
        week_start_at = datetime.combine(week_start, time.min)
        week_end_at = datetime.combine(
            selected_week_date + timedelta(days=1),
            time.min,
        )
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
            .where(RetrievedShort.channel_id == selected_channel)
            .where(RetrievedShort.published_at >= week_start_at)
            .where(RetrievedShort.published_at < week_end_at)
            .order_by(RetrievedShort.published_at.desc())
        ).all()
        shorts = serialize_dashboard_rows(raw_rows)

    weekly_stats = build_weekly_stats(shorts)
    chart_data = build_chart_data(weekly_stats)
    shorts_table = build_shorts_table(shorts)

    context = {
        "request": request,
        "generated_at": format_date_ru(datetime.now(UTC).date()),
        "weekly_stats": weekly_stats,
        "available_weeks": available_weeks,
        "channel_options": channel_options,
        "selected_channel": selected_channel or "",
        "selected_week": selected_week or "",
        "selected_week_label": selected_week_label,
        "chart_data": chart_data,
        "shorts_table": shorts_table,
    }
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=context,
    )
