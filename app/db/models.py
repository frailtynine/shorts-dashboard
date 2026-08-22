from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Theme(Base):
    __tablename__ = "themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    shorts: Mapped[list["RetrievedShort"]] = relationship(
        back_populates="theme"
    )


class RetrievedShort(Base):
    """Single Short item fetched through yt_dlp retrieval flows."""

    __tablename__ = "retrieved_shorts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    video_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    channel_id: Mapped[str] = mapped_column(String(128), index=True)
    channel_title: Mapped[str] = mapped_column(String(512), default="")
    title: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str] = mapped_column(String(4096), default="")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    theme_id: Mapped[int | None] = mapped_column(ForeignKey("themes.id"))
    thumbnail_url: Mapped[str] = mapped_column(String(1024), default="")
    webpage_url: Mapped[str] = mapped_column(String(1024), default="")
    views_timeline: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
    )
    likes_timeline: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
    )
    comments_timeline: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    theme: Mapped["Theme | None"] = relationship(back_populates="shorts")

    @property
    def theme_name(self) -> str | None:
        if not self.theme:
            return None
        return self.theme.name

    def add_view_point(self, views: int, at: datetime) -> None:
        """Append a chart point in x/y format."""
        self.views_timeline = self._append_metric_point(
            timeline=self.views_timeline,
            value=views,
            at=at,
        )

    def add_like_point(self, likes: int, at: datetime) -> None:
        """Append a like_count chart point in x/y format."""
        self.likes_timeline = self._append_metric_point(
            timeline=self.likes_timeline,
            value=likes,
            at=at,
        )

    def add_comment_point(self, comments: int, at: datetime) -> None:
        """Append a comment_count chart point in x/y format."""
        self.comments_timeline = self._append_metric_point(
            timeline=self.comments_timeline,
            value=comments,
            at=at,
        )

    def _append_metric_point(
        self,
        timeline: list[dict[str, Any]] | None,
        value: int,
        at: datetime,
    ) -> list[dict[str, Any]]:
        points = list(timeline or [])
        point = {"x": at.isoformat(), "y": int(value)}
        if points and points[-1] == point:
            return points
        points.append(point)
        return points


class ChannelOverview(Base):
    """Channel-level data and view chart points from hourly updates."""

    __tablename__ = "channel_overviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
    )
    channel_title: Mapped[str] = mapped_column(String(512), default="")
    channel_url: Mapped[str] = mapped_column(String(1024), default="")
    uploader_id: Mapped[str] = mapped_column(String(256), default="")
    uploader_url: Mapped[str] = mapped_column(String(1024), default="")
    description: Mapped[str] = mapped_column(String(4096), default="")
    channel_follower_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    playlist_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    views_timeline: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def add_view_point(self, views: int, at: datetime) -> None:
        """Append a chart point in x/y format."""
        points = list(self.views_timeline or [])
        point = {"x": at.isoformat(), "y": int(views)}
        if points and points[-1] == point:
            self.views_timeline = points
            return
        points.append(point)
        self.views_timeline = points
