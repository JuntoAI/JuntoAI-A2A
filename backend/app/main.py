"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import FirestoreConnectionError, SessionNotFoundError
from app.routers.health import router as health_router
from app.routers.models import router as models_router
from app.routers.negotiation import router as negotiation_router
from app.scenarios.router import router as scenarios_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log startup info."""
    logger.info(
        "Starting JuntoAI A2A API v%s [env=%s] CORS origins=%s",
        settings.APP_VERSION,
        settings.ENVIRONMENT,
        settings.cors_origins_list,
    )
    yield


app = FastAPI(title="JuntoAI A2A API", version=settings.APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Cache-Control"],
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(models_router)
api_router.include_router(negotiation_router)
api_router.include_router(scenarios_router)

app.include_router(api_router)


@app.exception_handler(SessionNotFoundError)
async def session_not_found_handler(request: Request, exc: SessionNotFoundError):
    """Return 404 when a session is not found."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(FirestoreConnectionError)
async def firestore_connection_handler(
    request: Request, exc: FirestoreConnectionError
):
    """Return 503 when Firestore is unavailable."""
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})
