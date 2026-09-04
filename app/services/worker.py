import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.services.channel_overview import ChannelOverviewService
from app.services.youtube_api_processing import YoutubeAPIProcessingService

logger = logging.getLogger(__name__)


def run_youtube_retrieval() -> None:
    settings = get_settings()
    channels = settings.sync_channels
    service = ChannelOverviewService()

    if not channels:
        logger.info("youtube retrieval skipped: no sync channels configured")
        return

    logger.info(
        "youtube retrieval started: channels=%s",
        len(channels),
    )

    for index, channel_id in enumerate(channels):
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

        if index < len(channels) - 1:
            time.sleep(settings.youtube_retrieval_channel_pause_seconds)

    logger.info("youtube retrieval cycle completed")


def run_ai_processing() -> None:
    settings = get_settings()
    channels = settings.sync_channels
    service = YoutubeAPIProcessingService()

    if not channels:
        logger.info(
            "shorts ai processing skipped: no sync channels configured"
        )
        return

    try:
        for channel_id in channels:
            logger.info(
                "shorts ai processing channel started: channel_id=%s",
                channel_id,
            )
            service.process_channel(
                channel_id,
                settings.sync_theme_scan_limit,
            )
            logger.info(
                "shorts ai processing channel finished: channel_id=%s",
                channel_id,
            )

        logger.info("shorts ai processing cycle completed")
    except Exception:
        logger.exception(
            "shorts ai processing failed: scan_limit=%s",
            settings.sync_theme_scan_limit,
        )


class AppWorker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.scheduler = BackgroundScheduler()

    def start(self) -> None:
        self.scheduler.add_job(
            run_youtube_retrieval,
            trigger="interval",
            seconds=self.settings.youtube_retrieval_interval_seconds,
            id="youtube_retrieval",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        self.scheduler.add_job(
            run_ai_processing,
            trigger="interval",
            seconds=self.settings.ai_processing_interval_seconds,
            id="shorts_ai_processing",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        self.scheduler.start()
        logger.info(
            "app worker started: retrieval_interval_seconds=%s "
            "ai_interval_seconds=%s",
            self.settings.youtube_retrieval_interval_seconds,
            self.settings.ai_processing_interval_seconds,
        )

    def stop(self) -> None:
        if not self.scheduler.running:
            return

        self.scheduler.shutdown(wait=False)
        logger.info("app worker stopped")


worker = AppWorker()
