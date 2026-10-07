import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class GeoProcessingError(Exception):
    """Raised when geospatial processing fails."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class FileValidationError(Exception):
    """Raised when file validation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class CRSError(Exception):
    """Raised when CRS detection or transformation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for consistent error responses."""

    @app.exception_handler(GeoProcessingError)
    async def geo_processing_handler(
        request: Request, exc: GeoProcessingError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "processing_error", "detail": exc.message},
        )

    @app.exception_handler(FileValidationError)
    async def file_validation_handler(
        request: Request, exc: FileValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": "validation_error", "detail": exc.message},
        )

    @app.exception_handler(CRSError)
    async def crs_error_handler(
        request: Request, exc: CRSError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "crs_error", "detail": exc.message},
        )

    @app.exception_handler(Exception)
    async def generic_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "detail": "An unexpected error occurred.",
            },
        )
