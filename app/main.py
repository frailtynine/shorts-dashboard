import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.services.worker import worker


logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure application logging for local app runs."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(logging.INFO)
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    worker.start()
    try:
        yield
    finally:
        worker.stop()


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="YouTube Analytics API",
        lifespan=lifespan,
    )
    app.include_router(api_router)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    return app


app = create_app()
