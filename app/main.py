"""Main application entrypoint for the Geospatial Measurement API."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse as FastFileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes.files import router as files_router
from app.utils.exceptions import register_exception_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup directories
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path("data").mkdir(parents=True, exist_ok=True)
    Path("static").mkdir(parents=True, exist_ok=True)
    logger.info("Geospatial Measurement API initialized.")
    yield


app = FastAPI(
    title="Geospatial File Measurement API",
    description=(
        "High-performance backend service for reading Shapefile (.zip) and KML files, "
        "auto-projecting geographic coordinates to metric UTM CRS, "
        "and computing geometric measurements."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
register_exception_handlers(app)

# Include API Routers
app.include_router(files_router)

# Mount static files
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = Path("static/index.html")
    if index_file.exists():
        return FastFileResponse(index_file)
    return {"message": "Geospatial Measurement API is running. Visit /docs for Swagger UI."}


@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok", "service": "Geospatial Measurement API", "version": "1.0.0"}
