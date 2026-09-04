from datetime import UTC, datetime

import httpx

from app.core.config import get_settings
from app.schemas.models import RetrievedShortSchema, RetrievedShortUpdate
from app.services.channel_overview import ChannelOverviewService
from app.services.utils import (
    chunked,
    parse_iso8601_duration,
    pick_thumbnail_url,
)


class YoutubeAPIProcessingService:
    def __init__(
        self,
        channel_service: ChannelOverviewService | None = None,
    ) -> None:
        self.channel_service = channel_service or ChannelOverviewService()

    def process_channel(self, channel_id: str, limit: int) -> None:
        shorts = self.channel_service.get_latest_shorts_without_theme(
            channel_id,
            limit,
        )
        if not shorts:
            return

        full_data, failed_video_ids = self.retrieve_full_short_data(shorts)
        self.channel_service.save_full_short_data(full_data)
        self.channel_service.mark_shorts_as_not_processed(failed_video_ids)

        described_shorts = (
            self.channel_service.get_latest_described_shorts_without_theme(
                channel_id,
                limit,
            )
        )
        theme_names = self.channel_service.get_theme_names()

        for batch in chunked(described_shorts, 10):
            batch_result = self.channel_service.choose_themes_for_batch(
                batch,
                list(theme_names),
            )
            for video_id, theme_name in batch_result:
                self.channel_service.save_short_theme(video_id, theme_name)
                if theme_name not in theme_names:
                    theme_names.append(theme_name)

    def retrieve_full_short_data(
        self,
        shorts: list[RetrievedShortSchema],
    ) -> tuple[list[tuple[str, RetrievedShortUpdate]], list[str]]:
        if not shorts:
            return [], []

        video_ids = [short.video_id for short in shorts]
        short_map = {short.video_id: short for short in shorts}
        items = self._fetch_youtube_video_details(video_ids)
        result: list[tuple[str, RetrievedShortUpdate]] = []
        returned_video_ids: set[str] = set()

        for item in items:
            video_id = item.get("id")
            if not isinstance(video_id, str) or video_id not in short_map:
                continue

            returned_video_ids.add(video_id)
            short = short_map[video_id]
            snippet = item.get("snippet") or {}
            statistics = item.get("statistics") or {}
            content_details = item.get("contentDetails") or {}
            published_at = self._parse_published_at(snippet.get("publishedAt"))

            result.append(
                (
                    video_id,
                    RetrievedShortUpdate(
                        channel_id=short.channel_id,
                        channel_title=str(
                            snippet.get("channelTitle") or short.channel_title
                        ),
                        title=str(snippet.get("title") or ""),
                        description=str(snippet.get("description") or ""),
                        duration_seconds=parse_iso8601_duration(
                            str(content_details.get("duration") or "PT0S")
                        ),
                        published_at=published_at,
                        view_count=int(statistics.get("viewCount") or 0),
                        like_count=int(statistics.get("likeCount") or 0),
                        comment_count=int(statistics.get("commentCount") or 0),
                        thumbnail_url=pick_thumbnail_url(
                            snippet.get("thumbnails") or {}
                        ),
                        webpage_url=(
                            f"https://www.youtube.com/shorts/{video_id}"
                        ),
                        fetched_at=datetime.now(UTC),
                    ),
                )
            )

        failed_video_ids = [
            video_id for video_id in video_ids
            if video_id not in returned_video_ids
        ]
        return result, failed_video_ids

    def _fetch_youtube_video_details(
        self,
        video_ids: list[str],
    ) -> list[dict]:
        api_key = get_settings().youtube_api_key
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY is not configured.")

        items: list[dict] = []
        for batch in chunked(video_ids, 50):
            response = httpx.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,contentDetails,statistics",
                    "id": ",".join(batch),
                    "key": api_key,
                },
                timeout=3.0,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                raise ValueError(str(payload["error"]))
            items.extend(payload.get("items") or [])
        return items

    def _parse_published_at(self, value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        return datetime.fromisoformat(value)
