from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TimelinePoint(BaseModel):
    x: str
    y: int


class ThemeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class RetrievedShortBase(BaseModel):
    video_id: str
    channel_id: str
    channel_title: str = ""
    title: str = ""
    description: str = ""
    duration_seconds: int = 0
    published_at: datetime | None = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    theme_id: int | None = None
    thumbnail_url: str = ""
    webpage_url: str = ""
    views_timeline: list[TimelinePoint] = Field(default_factory=list)
    likes_timeline: list[TimelinePoint] = Field(default_factory=list)
    comments_timeline: list[TimelinePoint] = Field(default_factory=list)


class RetrievedShortCreate(RetrievedShortBase):
    fetched_at: datetime | None = None


class RetrievedShortUpdate(BaseModel):
    channel_id: str | None = None
    channel_title: str | None = None
    title: str | None = None
    description: str | None = None
    duration_seconds: int | None = None
    published_at: datetime | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    theme_id: int | None = None
    thumbnail_url: str | None = None
    webpage_url: str | None = None
    views_timeline: list[TimelinePoint] | None = None
    likes_timeline: list[TimelinePoint] | None = None
    comments_timeline: list[TimelinePoint] | None = None
    fetched_at: datetime | None = None


class RetrievedShortSchema(RetrievedShortBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fetched_at: datetime
    theme_name: str | None = None


class ChannelOverviewBase(BaseModel):
    channel_id: str
    channel_title: str = ""
    channel_url: str = ""
    uploader_id: str = ""
    uploader_url: str = ""
    description: str = ""
    channel_follower_count: int | None = None
    playlist_count: int | None = None
    views_timeline: list[TimelinePoint] = Field(default_factory=list)


class ChannelOverviewCreate(ChannelOverviewBase):
    last_synced_at: datetime | None = None


class ChannelOverviewUpdate(BaseModel):
    channel_title: str | None = None
    channel_url: str | None = None
    uploader_id: str | None = None
    uploader_url: str | None = None
    description: str | None = None
    channel_follower_count: int | None = None
    playlist_count: int | None = None
    views_timeline: list[TimelinePoint] | None = None
    last_synced_at: datetime | None = None


class ChannelOverviewSchema(ChannelOverviewBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_synced_at: datetime


def timeline_points_to_dicts(
    points: list[TimelinePoint] | list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not points:
        return []

    return [
        point.model_dump() if isinstance(point, TimelinePoint) else dict(point)
        for point in points
    ]
