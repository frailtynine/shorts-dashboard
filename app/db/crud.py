from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import ChannelOverview, RetrievedShort, Theme
from app.schemas.models import (
    ChannelOverviewCreate,
    ChannelOverviewSchema,
    ChannelOverviewUpdate,
    RetrievedShortCreate,
    RetrievedShortSchema,
    RetrievedShortUpdate,
    timeline_points_to_dicts,
)


class RetrievedShortCRUD:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, video_id: str) -> RetrievedShortSchema | None:
        model = self.session.scalar(
            select(RetrievedShort)
            .options(joinedload(RetrievedShort.theme))
            .where(RetrievedShort.video_id == video_id)
        )
        if model is None:
            return None
        return RetrievedShortSchema.model_validate(model)

    def list_by_channel(self, channel_id: str) -> list[RetrievedShortSchema]:
        models = self.session.scalars(
            select(RetrievedShort)
            .options(joinedload(RetrievedShort.theme))
            .where(RetrievedShort.channel_id == channel_id)
            .order_by(RetrievedShort.published_at.desc())
        ).all()
        return [RetrievedShortSchema.model_validate(model) for model in models]

    def list_latest_without_theme(
        self,
        limit: int,
        channel_id: str,
    ) -> list[RetrievedShortSchema]:
        models = self.session.scalars(
            select(RetrievedShort)
            .options(joinedload(RetrievedShort.theme))
            .where(RetrievedShort.theme_id.is_(None))
            .where(RetrievedShort.channel_id == channel_id)
            .order_by(RetrievedShort.fetched_at.asc())
            .limit(limit)
        ).all()
        return [RetrievedShortSchema.model_validate(model) for model in models]

    def list_latest_described_without_theme(
        self,
        limit: int,
        channel_id: str,
    ) -> list[RetrievedShortSchema]:
        models = self.session.scalars(
            select(RetrievedShort)
            .options(joinedload(RetrievedShort.theme))
            .where(RetrievedShort.theme_id.is_(None))
            .where(RetrievedShort.description != "")
            .where(RetrievedShort.channel_id == channel_id)
            .order_by(RetrievedShort.fetched_at.desc())
            .limit(limit)
        ).all()
        return [RetrievedShortSchema.model_validate(model) for model in models]

    def create(self, payload: RetrievedShortCreate) -> RetrievedShortSchema:
        model = RetrievedShort(
            video_id=payload.video_id,
            channel_id=payload.channel_id,
            channel_title=payload.channel_title,
            title=payload.title,
            description=payload.description,
            duration_seconds=payload.duration_seconds,
            published_at=payload.published_at,
            view_count=payload.view_count,
            like_count=payload.like_count,
            comment_count=payload.comment_count,
            theme_id=payload.theme_id,
            thumbnail_url=payload.thumbnail_url,
            webpage_url=payload.webpage_url,
            views_timeline=timeline_points_to_dicts(payload.views_timeline),
            likes_timeline=timeline_points_to_dicts(payload.likes_timeline),
            comments_timeline=timeline_points_to_dicts(
                payload.comments_timeline
            ),
        )
        if payload.fetched_at is not None:
            model.fetched_at = payload.fetched_at

        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return RetrievedShortSchema.model_validate(model)

    def update(
        self, video_id: str,
        payload: RetrievedShortUpdate
    ) -> RetrievedShortSchema | None:
        model = self.session.scalar(
            select(RetrievedShort)
            .options(joinedload(RetrievedShort.theme))
            .where(RetrievedShort.video_id == video_id)
        )
        if model is None:
            return None

        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if field in {
                "views_timeline",
                "likes_timeline",
                "comments_timeline",
            }:
                value = timeline_points_to_dicts(value)
            setattr(model, field, value)

        self.session.flush()
        self.session.refresh(model)
        return RetrievedShortSchema.model_validate(model)

    def apply_full_data_update(
        self,
        video_id: str,
        payload: RetrievedShortUpdate,
    ) -> RetrievedShortSchema | None:
        model = self.session.scalar(
            select(RetrievedShort)
            .options(joinedload(RetrievedShort.theme))
            .where(RetrievedShort.video_id == video_id)
        )
        if model is None:
            return None

        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(model, field, value)

        if payload.fetched_at is not None:
            if payload.view_count is not None:
                model.add_view_point(payload.view_count, payload.fetched_at)
            if payload.like_count is not None:
                model.add_like_point(payload.like_count, payload.fetched_at)
            if payload.comment_count is not None:
                model.add_comment_point(payload.comment_count, payload.fetched_at)

        self.session.flush()
        self.session.refresh(model)
        return RetrievedShortSchema.model_validate(model)

    def delete(self, video_id: str) -> bool:
        model = self.session.scalar(
            select(RetrievedShort).where(RetrievedShort.video_id == video_id)
        )
        if model is None:
            return False

        self.session.delete(model)
        self.session.flush()
        return True


class ChannelOverviewCRUD:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, channel_id: str) -> ChannelOverviewSchema | None:
        model = self.session.scalar(
            select(ChannelOverview).where(
                ChannelOverview.channel_id == channel_id
            )
        )
        if model is None:
            return None
        return ChannelOverviewSchema.model_validate(model)

    def list_all(self) -> list[ChannelOverviewSchema]:
        models = self.session.scalars(
            select(ChannelOverview).order_by(
                ChannelOverview.channel_title.asc()
            )
        ).all()
        return [
            ChannelOverviewSchema.model_validate(model)
            for model in models
        ]

    def create(self, payload: ChannelOverviewCreate) -> ChannelOverviewSchema:
        model = ChannelOverview(
            channel_id=payload.channel_id,
            channel_title=payload.channel_title,
            channel_url=payload.channel_url,
            uploader_id=payload.uploader_id,
            uploader_url=payload.uploader_url,
            description=payload.description,
            channel_follower_count=payload.channel_follower_count,
            playlist_count=payload.playlist_count,
            views_timeline=timeline_points_to_dicts(payload.views_timeline),
        )
        if payload.last_synced_at is not None:
            model.last_synced_at = payload.last_synced_at

        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return ChannelOverviewSchema.model_validate(model)

    def update(
        self,
        channel_id: str,
        payload: ChannelOverviewUpdate,
    ) -> ChannelOverviewSchema | None:
        model = self.session.scalar(
            select(ChannelOverview).where(
                ChannelOverview.channel_id == channel_id
            )
        )
        if model is None:
            return None

        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if field == "views_timeline":
                value = timeline_points_to_dicts(value)
            setattr(model, field, value)

        self.session.flush()
        self.session.refresh(model)
        return ChannelOverviewSchema.model_validate(model)

    def save_with_view_point(
        self,
        payload: ChannelOverviewCreate,
        view_count: int,
    ) -> ChannelOverviewSchema:
        model = self.session.scalar(
            select(ChannelOverview).where(
                ChannelOverview.channel_id == payload.channel_id
            )
        )

        if model is None:
            model = ChannelOverview(
                channel_id=payload.channel_id,
                channel_title=payload.channel_title,
                channel_url=payload.channel_url,
                uploader_id=payload.uploader_id,
                uploader_url=payload.uploader_url,
                description=payload.description,
                channel_follower_count=payload.channel_follower_count,
                playlist_count=payload.playlist_count,
                views_timeline=[],
            )
            self.session.add(model)
        else:
            model.channel_title = payload.channel_title
            model.channel_url = payload.channel_url
            model.uploader_id = payload.uploader_id
            model.uploader_url = payload.uploader_url
            model.description = payload.description
            model.channel_follower_count = payload.channel_follower_count
            model.playlist_count = payload.playlist_count

        if payload.last_synced_at is not None:
            model.last_synced_at = payload.last_synced_at
            model.add_view_point(view_count, payload.last_synced_at)

        self.session.flush()
        self.session.refresh(model)
        return ChannelOverviewSchema.model_validate(model)

    def delete(self, channel_id: str) -> bool:
        model = self.session.scalar(
            select(ChannelOverview).where(
                ChannelOverview.channel_id == channel_id
            )
        )
        if model is None:
            return False

        self.session.delete(model)
        self.session.flush()
        return True


class ThemeCRUD:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_name(self, name: str):
        return self.session.scalar(
            select(Theme).where(Theme.name == name)
        )

    def list_names(self) -> list[str]:
        return self.session.scalars(
            select(Theme.name).order_by(Theme.name.asc())
        ).all()

    def create(self, name: str):
        model = Theme(name=name)
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return model
