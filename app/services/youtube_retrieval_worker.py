import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.services.channel_overview import ChannelOverviewService


logger = logging.getLogger(__name__)


def run_youtube_retrieval() -> None:
    settings = get_settings()
    channels = settings.sync_channels

    if not channels:
        logger.info("youtube retrieval skipped: no sync channels configured")
        return

    service = ChannelOverviewService()
    logger.info(
        "youtube retrieval started: channels=%s",
        len(channels),
    )

    for channel_id in channels:
        logger.info(
            "youtube retrieval processing channel: channel_id=%s",
            channel_id,
        )
        try:
            service.process_channel(channel_id)
        except Exception:
            logger.exception(
                "youtube retrieval failed: channel_id=%s",
                channel_id,
            )
        else:
            logger.info(
                "youtube retrieval finished channel: channel_id=%s",
                channel_id,
            )

    logger.info("youtube retrieval cycle completed")


def run_shorts_ai_processing() -> None:
    settings = get_settings()
    service = ChannelOverviewService()

    try:
        shorts = service.get_latest_shorts_without_theme(
            settings.sync_theme_scan_limit
        )

        if not shorts:
            logger.info(
                "shorts ai processing skipped: no shorts without themes"
            )
            return

        logger.info(
            "shorts ai processing started: shorts=%s",
            len(shorts),
        )

        full_data, failed_video_ids = service.retrieve_full_short_data(shorts)
        service.save_full_short_data(full_data)
        service.mark_shorts_as_not_processed(failed_video_ids)

        shorts = service.get_latest_described_shorts_without_theme(
            settings.sync_theme_scan_limit
        )
        theme_names = service.get_theme_names()

        for offset in range(0, len(shorts), 10):
            batch = shorts[offset:offset + 10]
            logger.info(
                "shorts ai processing batch started: offset=%s size=%s",
                offset,
                len(batch),
            )
            batch_result = service.choose_themes_for_batch(
                batch,
                list(theme_names),
            )

            for video_id, theme_name in batch_result:
                service.save_short_theme(video_id, theme_name)
                if theme_name not in theme_names:
                    theme_names.append(theme_name)

            logger.info(
                "shorts ai processing batch finished: offset=%s size=%s",
                offset,
                len(batch),
            )

        logger.info("shorts ai processing cycle completed")
    except Exception:
        logger.exception(
            "shorts ai processing failed: scan_limit=%s",
            settings.sync_theme_scan_limit,
        )


class YoutubeRetrievalWorker:
    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = settings.sync_worker_enabled
        self.interval_seconds = settings.sync_interval_seconds
        self.scheduler = BackgroundScheduler()

    def start(self) -> None:
        if not self.enabled:
            logger.info("youtube retrieval worker disabled")
            return

        self.scheduler.add_job(
            run_youtube_retrieval,
            trigger="interval",
            seconds=self.interval_seconds,
            id="youtube_retrieval",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        self.scheduler.add_job(
            run_shorts_ai_processing,
            trigger="interval",
            seconds=self.interval_seconds,
            id="shorts_ai_processing",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        self.scheduler.start()
        logger.info(
            "youtube retrieval worker started: interval_seconds=%s",
            self.interval_seconds,
        )

    def stop(self) -> None:
        if not self.scheduler.running:
            return

        self.scheduler.shutdown(wait=False)
        logger.info("youtube retrieval worker stopped")
