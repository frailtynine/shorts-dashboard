from fastapi import APIRouter

from app.api.routers.dashboard import router as dashboard_router


api_router = APIRouter(prefix="/api")
api_router.include_router(dashboard_router)
