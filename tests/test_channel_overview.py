import json
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

import app.api.routers.dashboard as dashboard_module
import app.services.channel_overview as channel_overview_module
import app.services.youtube_api_processing as youtube_api_processing_module
from app.core.config import Settings
from app.db.crud import ChannelOverviewCRUD, RetrievedShortCRUD
from app.schemas.models import ChannelOverviewCreate, RetrievedShortCreate
from app.services.utils import parse_iso8601_duration


class FakeYoutubeDL:
    def __init__(self, opts: dict, info: dict | None, error: Exception | None):
        self.opts = opts
        self.info = info
        self.error = error
        self.calls: list[tuple[str, bool]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url: str, download: bool = False):
        self.calls.append((url, download))
        if self.error is not None:
            raise self.error
        return self.info


def install_fake_ytdlp(
    monkeypatch: pytest.MonkeyPatch,
    *,
    info: dict | None,
    error: Exception | None = None,
) -> FakeYoutubeDL:
    state: dict[str, FakeYoutubeDL] = {}

    def fake_youtube_dl(opts: dict) -> FakeYoutubeDL:
        client = FakeYoutubeDL(opts=opts, info=info, error=error)
        state["client"] = client
        return client

    monkeypatch.setattr(
        channel_overview_module.yt_dlp,
        "YoutubeDL",
        fake_youtube_dl,
    )
    return state


class FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def build_channel_overview(channel_id: str) -> ChannelOverviewCreate:
    return ChannelOverviewCreate(
        channel_id=channel_id,
        channel_title="Test Channel",
        description="Channel description",
        channel_follower_count=1200,
        playlist_count=5,
    )


def build_short(video_id: str, channel_id: str) -> RetrievedShortCreate:
    return RetrievedShortCreate(
        video_id=video_id,
        channel_id=channel_id,
        channel_title="Test Channel",
        title=f"Title for {video_id}",
        view_count=100,
        like_count=10,
        comment_count=1,
    )


def install_test_session_scope(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    @contextmanager
    def fake_session_scope():
        yield db_session

    monkeypatch.setattr(
        channel_overview_module,
        "session_scope",
        fake_session_scope,
    )


def test_get_channel_data_builds_expected_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = install_fake_ytdlp(
        monkeypatch,
        info={
            "title": "Test Channel",
            "subscriber_count": 1200,
            "video_count": 5,
            "view_count": 44000,
            "description": "Channel description",
            "thumbnail": "https://img.test/channel.jpg",
            "entries": [
                {"id": "short-1", "title": "First short"},
                {"id": "short-2", "title": "Second short"},
            ],
        },
    )

    payload = channel_overview_module.ChannelOverviewService().get_channel_data(
        "channel-123"
    )
    assert set(payload) == {"channel_overview", "entries", "view_count"}
    assert payload["channel_overview"].channel_id == "channel-123"
    assert payload["channel_overview"].channel_title == "Test Channel"
    assert payload["view_count"] == 44000
    assert payload["entries"][0].video_id == "short-1"
    assert payload["entries"][0].title == "First short"
    assert payload["entries"][1].video_id == "short-2"
    assert state["client"].calls == [
        ("https://www.youtube.com/channel-123/shorts", False)
    ]


def test_get_channel_data_returns_empty_entries_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_ytdlp(
        monkeypatch,
        info={
            "title": "Empty Channel",
            "entries": [],
        },
    )

    payload = channel_overview_module.ChannelOverviewService().get_channel_data(
        "empty-channel"
    )

    assert payload["channel_overview"].channel_id == "empty-channel"
    assert payload["entries"] == []


def test_get_channel_data_raises_for_missing_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_ytdlp(monkeypatch, info=None)

    with pytest.raises(ValueError, match="missing-channel"):
        channel_overview_module.ChannelOverviewService().get_channel_data(
            "missing-channel"
        )


def test_get_channel_data_propagates_inaccessible_channel_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_ytdlp(
        monkeypatch,
        info=None,
        error=RuntimeError("Channel is inaccessible"),
    )

    with pytest.raises(RuntimeError, match="inaccessible"):
        channel_overview_module.ChannelOverviewService().get_channel_data(
            "blocked-channel"
        )


def test_save_channel_data_creates_channel_in_db(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overview = build_channel_overview("new-channel")
    install_test_session_scope(monkeypatch, db_session)

    channel_overview_module.ChannelOverviewService().save_channel_data(
        overview
    )
    db_session.commit()
    db_session.expire_all()

    saved = ChannelOverviewCRUD(db_session).get("new-channel")

    assert saved is not None
    assert saved.channel_id == "new-channel"
    assert saved.channel_title == "Test Channel"
    assert saved.description == "Channel description"
    assert saved.channel_follower_count == 1200
    assert saved.playlist_count == 5


def test_save_channel_data_updates_existing_channel_in_db(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ChannelOverviewCRUD(db_session).create(
        build_channel_overview("existing-channel")
    )
    db_session.commit()
    db_session.expire_all()

    overview = ChannelOverviewCreate(
        channel_id="existing-channel",
        channel_title="Updated Channel",
        description="Updated description",
        channel_follower_count=9000,
        playlist_count=17,
    )

    install_test_session_scope(monkeypatch, db_session)

    channel_overview_module.ChannelOverviewService().save_channel_data(
        overview
    )
    db_session.commit()
    db_session.expire_all()

    saved = ChannelOverviewCRUD(db_session).get("existing-channel")

    assert saved is not None
    assert saved.channel_title == "Updated Channel"
    assert saved.description == "Updated description"
    assert saved.channel_follower_count == 9000
    assert saved.playlist_count == 17


def test_save_shorts_from_channel_overview_creates_new_short_in_db(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_test_session_scope(monkeypatch, db_session)

    channel_overview_module.ChannelOverviewService(
    ).save_shorts_from_channel_overview(
        "channel-123",
        [build_short("short-1", "channel-123")],
    )
    db_session.commit()
    db_session.expire_all()

    saved = RetrievedShortCRUD(db_session).get("short-1")

    assert saved is not None
    assert saved.video_id == "short-1"
    assert saved.channel_id == "channel-123"
    assert saved.title == "Title for short-1"
    assert saved.view_count == 100


def test_save_shorts_from_channel_overview_updates_existing_short_in_db(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    RetrievedShortCRUD(db_session).create(
        build_short("short-1", "channel-123")
    )
    db_session.commit()
    db_session.expire_all()

    install_test_session_scope(monkeypatch, db_session)

    updated_short = RetrievedShortCreate(
        video_id="short-1",
        channel_id="channel-123",
        channel_title="Updated Channel",
        title="Updated title",
        view_count=999,
        like_count=44,
        comment_count=5,
    )

    channel_overview_module.ChannelOverviewService(
    ).save_shorts_from_channel_overview(
        "channel-123",
        [updated_short],
    )
    db_session.commit()
    db_session.expire_all()

    saved = RetrievedShortCRUD(db_session).get("short-1")

    assert saved is not None
    assert saved.channel_title == "Updated Channel"
    assert saved.title == "Updated title"
    assert saved.view_count == 999
    assert saved.like_count == 44
    assert saved.comment_count == 5


def test_retrieve_full_short_data_uses_youtube_data_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []
    fixture_path = Path(__file__).parent / "fixtures" / "youtube_video_list_response.json"
    fixture_payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    def fake_get(url: str, params: dict, timeout: float) -> FakeHTTPResponse:
        calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeHTTPResponse(fixture_payload)

    monkeypatch.setattr(youtube_api_processing_module.httpx, "get", fake_get)
    monkeypatch.setattr(
        youtube_api_processing_module,
        "get_settings",
        lambda: type("Settings", (), {"youtube_api_key": "test-key"})(),
    )

    service = youtube_api_processing_module.YoutubeAPIProcessingService()
    result, failed = service.retrieve_full_short_data(
        [build_short("JxhSF-Zz5zs", "channel-123")]
    )

    assert failed == []
    assert len(result) == 1
    video_id, payload = result[0]
    assert video_id == "JxhSF-Zz5zs"
    assert payload.title == "Блэкаут в Москве сломал интернет по всей России"
    assert payload.description.startswith("Отключение электричества")
    assert payload.channel_title == "Ходорковский LIVE"
    assert payload.duration_seconds == 39
    assert payload.view_count == 115859
    assert payload.like_count == 2855
    assert payload.comment_count == 183
    assert payload.thumbnail_url == (
        "https://i.ytimg.com/vi/JxhSF-Zz5zs/maxresdefault.jpg"
    )
    assert payload.webpage_url == "https://www.youtube.com/shorts/JxhSF-Zz5zs"
    assert calls[0]["params"]["id"] == "JxhSF-Zz5zs"


def test_retrieve_full_short_data_marks_missing_items_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        youtube_api_processing_module.httpx,
        "get",
        lambda url, params, timeout: FakeHTTPResponse({"items": []}),
    )
    monkeypatch.setattr(
        youtube_api_processing_module,
        "get_settings",
        lambda: type("Settings", (), {"youtube_api_key": "test-key"})(),
    )

    service = youtube_api_processing_module.YoutubeAPIProcessingService()
    result, failed = service.retrieve_full_short_data(
        [build_short("short-404", "channel-123")]
    )

    assert result == []
    assert failed == ["short-404"]


def test_retrieve_full_short_data_requires_api_key() -> None:
    youtube_api_processing_module.get_settings = lambda: type(
        "Settings", (), {"youtube_api_key": ""}
    )()
    service = youtube_api_processing_module.YoutubeAPIProcessingService()

    with pytest.raises(ValueError, match="YOUTUBE_API_KEY"):
        service.retrieve_full_short_data([build_short("short-1", "channel-123")])


def test_parse_iso8601_duration_handles_short_values() -> None:
    assert parse_iso8601_duration("PT59S") == 59
    assert parse_iso8601_duration("PT1M2S") == 62
    assert parse_iso8601_duration("PT2H3M4S") == 7384


def test_dashboard_defaults_to_first_configured_channel_latest_week(
    client,
    db_session: Session,
) -> None:
    first_short = RetrievedShortCreate(
        video_id="first-short",
        channel_id="first-channel",
        channel_title="First Channel",
        title="Latest short",
        view_count=100,
        like_count=10,
        comment_count=1,
        duration_seconds=35,
        published_at=datetime.fromisoformat("2026-09-03T10:00:00+00:00"),
    )
    second_short = RetrievedShortCreate(
        video_id="second-short",
        channel_id="second-channel",
        channel_title="Second Channel",
        title="Other short",
        view_count=200,
        like_count=20,
        comment_count=2,
        duration_seconds=40,
        published_at=datetime.fromisoformat("2026-09-10T10:00:00+00:00"),
    )
    RetrievedShortCRUD(db_session).create(first_short)
    RetrievedShortCRUD(db_session).create(second_short)
    db_session.commit()

    dashboard_module.get_settings = lru_cache(
        lambda: Settings(
            sync_channels=["first-channel", "second-channel"],
        )
    )

    response = client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "Latest short" in body
    assert "Other short" not in body
    assert 'window.SELECTED_CHANNEL = "first-channel"' in body
    assert 'window.SELECTED_WEEK = "2026-09-06"' in body


def test_dashboard_filters_by_channel_and_week(
    client,
    db_session: Session,
) -> None:
    RetrievedShortCRUD(db_session).create(
        RetrievedShortCreate(
            video_id="week-one",
            channel_id="first-channel",
            channel_title="First Channel",
            title="Week one short",
            view_count=100,
            like_count=10,
            comment_count=1,
            duration_seconds=35,
            published_at=datetime.fromisoformat("2026-09-01T10:00:00+00:00"),
        )
    )
    RetrievedShortCRUD(db_session).create(
        RetrievedShortCreate(
            video_id="week-two",
            channel_id="first-channel",
            channel_title="First Channel",
            title="Week two short",
            view_count=300,
            like_count=30,
            comment_count=3,
            duration_seconds=45,
            published_at=datetime.fromisoformat("2026-09-10T10:00:00+00:00"),
        )
    )
    RetrievedShortCRUD(db_session).create(
        RetrievedShortCreate(
            video_id="other-channel",
            channel_id="second-channel",
            channel_title="Second Channel",
            title="Other channel short",
            view_count=500,
            like_count=50,
            comment_count=5,
            duration_seconds=55,
            published_at=datetime.fromisoformat("2026-09-10T10:00:00+00:00"),
        )
    )
    db_session.commit()

    dashboard_module.get_settings = lru_cache(
        lambda: Settings(sync_channels=["first-channel", "second-channel"])
    )

    response = client.get(
        "/",
        params={"channel": "first-channel", "week": "2026-09-13"},
    )

    assert response.status_code == 200
    body = response.text
    assert "Week two short" in body
    assert "Week one short" not in body
    assert "Other channel short" not in body
    assert 'window.SELECTED_CHANNEL = "first-channel"' in body
    assert 'window.SELECTED_WEEK = "2026-09-13"' in body
    assert "31 августа 2026 - 6 сентября 2026" in body
    assert '"weekly_views": [100, 300]' in body
