import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.routes import router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s...", settings.app_name)
    if not settings.api_key:
        logger.warning("API_KEY not set — all /api/ endpoints are unprotected!")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="AI-powered document extraction for Dutch invoices and receipts",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    """Require API key for all /api/ routes. Health and CORS preflight are public."""
    if (
        request.url.path.startswith("/api/")
        and request.method != "OPTIONS"  # Let CORS preflight through
        and settings.api_key
    ):
        provided = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not provided or not secrets.compare_digest(provided, settings.api_key):
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)


app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": settings.app_name}
