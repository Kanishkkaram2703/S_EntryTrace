"""S*EntryTrace — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import devices, findings, health, reports, scans
from backend.app.config import settings
from backend.app.logging_config import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure output directories exist on startup."""
    settings.ensure_directories()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Android digital-forensics desktop workstation backend. "
        "Wraps the MVT forensic engine with safe ADB device management."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route groups
app.include_router(health.router)
app.include_router(devices.router)
app.include_router(scans.router)
app.include_router(findings.router)
app.include_router(reports.router)
