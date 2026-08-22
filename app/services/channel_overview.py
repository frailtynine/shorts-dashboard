from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import yt_dlp

from app.ai.client import AIProcessor
from app.db.crud import ChannelOverviewCRUD, RetrievedShortCRUD, ThemeCRUD
from app.db.session import session_scope
from app.schemas.models import (
    ChannelOverviewCreate,
    RetrievedShortCreate,
    RetrievedShortSchema,
    RetrievedShortUpdate,
)


class ChannelOverviewService:

    def get_channel_data(self, channel_id: str) -> dict:

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "force_generic_extractor": True,
            "js_runtimes": {
                "node": {}
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f'https://www.youtube.com/{channel_id}/shorts', download=False
            )
            if info is None:
                raise ValueError(f"Channel with ID {channel_id} not found.")
            channel_overview = ChannelOverviewCreate(
                channel_id=channel_id,
                channel_title=info.get("title", ""),
                subscriber_count=info.get("subscriber_count", 0),
                video_count=info.get("video_count", 0),
                view_count=info.get("view_count", 0),
                description=info.get("description", ""),
                profile_image_url=info.get("thumbnail", ""),
                last_synced_at=datetime.now(timezone.utc)
            )
            entries = [
                RetrievedShortCreate(
                    video_id=entry.get("id"),
                    channel_id=channel_id,
                    title=entry.get("title"),
                    view_count=entry.get("view_count", 0),
                    fetched_at=datetime.now(timezone.utc),
                    channel_title=channel_overview.channel_title

                ) for entry in info.get("entries")
            ]
        return {
            "channel_overview": channel_overview,
            "entries": entries,
            "view_count": int(info.get("view_count") or 0),
        }

    def save_channel_data(
        self,
        channel_overview: ChannelOverviewCreate,
        view_count: int = 0,
    ):
        with session_scope() as session:
            channel_crud = ChannelOverviewCRUD(session)
            channel_crud.save_with_view_point(
                channel_overview,
                view_count
            )

    def save_shorts_from_channel_overview(
        self,
        channel_id: str,
        payload_list: list[RetrievedShortCreate]
    ) -> None:
        with session_scope() as session:
            shorts_crud = RetrievedShortCRUD(session)
            all_shorts = shorts_crud.list_by_channel(
                channel_id
            )
            all_shorts_ids = [item.video_id for item in all_shorts]
            for retrieved_short in payload_list:
                if retrieved_short.video_id in all_shorts_ids:
                    shorts_crud.update(
                        retrieved_short.video_id,
                        retrieved_short
                    )
                else:
                    shorts_crud.create(retrieved_short)
                all_shorts_ids.append(retrieved_short.video_id)

    def retrieve_full_short_data(
        self,
        shorts: list[RetrievedShortSchema],
    ) -> tuple[list[tuple[str, RetrievedShortUpdate]], list[str]]:
        ydl_opts = {
            'skip_download': True,
            'js_runtimes': {
                'node': {}
            }
        }
        result: list[tuple[str, RetrievedShortUpdate]] = []
        failed_video_ids: list[str] = []
        with yt_dlp.YoutubeDL(ydl_opts) as ytd:
            for short in shorts:
                try:
                    info = ytd.extract_info(
                        f"https://youtube.com/shorts/{short.video_id}",
                        download=False,
                    )
                except Exception:
                    failed_video_ids.append(short.video_id)
                    continue

                if not info:
                    failed_video_ids.append(short.video_id)
                    continue

                published_at = None
                timestamp = info.get("timestamp")
                if timestamp is not None:
                    published_at = datetime.fromtimestamp(
                        timestamp,
                        tz=timezone.utc,
                    )

                result.append(
                    (
                        short.video_id,
                        RetrievedShortUpdate(
                            channel_id=short.channel_id,
                            channel_title=info.get("channel", ""),
                            title=info.get("title", ""),
                            description=info.get("description", ""),
                            duration_seconds=int(info.get("duration", 0)),
                            published_at=published_at,
                            view_count=int(info.get("view_count", 0)),
                            like_count=int(info.get("like_count", 0)),
                            comment_count=int(info.get("comment_count", 0)),
                            thumbnail_url=info.get("thumbnail", ""),
                            webpage_url=info.get("webpage_url", ""),
                            fetched_at=datetime.now(timezone.utc),
                        ),
                    )
                )
        return result, failed_video_ids

    def save_full_short_data(
        self,
        payload_list: list[tuple[str, RetrievedShortUpdate]],
    ) -> None:
        with session_scope() as session:
            shorts_crud = RetrievedShortCRUD(session)
            for video_id, payload in payload_list:
                shorts_crud.apply_full_data_update(video_id, payload)

    def mark_shorts_as_not_processed(
        self,
        video_ids: list[str],
    ) -> None:
        if not video_ids:
            return

        with session_scope() as session:
            theme_crud = ThemeCRUD(session)
            shorts_crud = RetrievedShortCRUD(session)
            theme = theme_crud.get_by_name("Не обработано")
            if theme is None:
                theme = theme_crud.create("Не обработано")

            for video_id in video_ids:
                shorts_crud.update(
                    video_id,
                    RetrievedShortUpdate(theme_id=theme.id),
                )

    def get_latest_shorts_without_theme(
        self,
        limit: int,
    ) -> list[RetrievedShortSchema]:
        with session_scope() as session:
            shorts_crud = RetrievedShortCRUD(session)
            return shorts_crud.list_latest_without_theme(limit)

    def get_latest_described_shorts_without_theme(
        self,
        limit: int,
    ) -> list[RetrievedShortSchema]:
        with session_scope() as session:
            shorts_crud = RetrievedShortCRUD(session)
            return shorts_crud.list_latest_described_without_theme(limit)

    def get_theme_names(self) -> list[str]:
        with session_scope() as session:
            theme_crud = ThemeCRUD(session)
            return theme_crud.list_names()

    def choose_themes_for_batch(
        self,
        shorts: list[RetrievedShortSchema],
        themes: list[str],
    ) -> list[tuple[str, str]]:
        if not shorts:
            return []

        with ThreadPoolExecutor(max_workers=min(10, len(shorts))) as executor:
            return list(
                executor.map(
                    lambda short: self.choose_theme_for_short(short, themes),
                    shorts,
                )
            )

    def choose_theme_for_short(
        self,
        short: RetrievedShortSchema,
        themes: list[str],
    ) -> tuple[str, str]:
        processor = AIProcessor()
        theme_name = processor.choose_theme_name(
            short.title,
            short.description,
            themes,
        )
        return short.video_id, theme_name

    def save_short_theme(self, video_id: str, theme_name: str) -> None:
        with session_scope() as session:
            theme_crud = ThemeCRUD(session)
            shorts_crud = RetrievedShortCRUD(session)
            theme = theme_crud.get_by_name(theme_name)
            if theme is None:
                theme = theme_crud.create(theme_name)
            shorts_crud.update(
                video_id,
                RetrievedShortUpdate(theme_id=theme.id),
            )

    def process_channel(self, channel_id: str):
        channel_data = self.get_channel_data(channel_id)
        self.save_channel_data(
            channel_data["channel_overview"],
            channel_data["view_count"],
        )
        self.save_shorts_from_channel_overview(
            channel_id,
            channel_data["entries"]
        )
