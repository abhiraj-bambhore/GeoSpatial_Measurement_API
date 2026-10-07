"""FastAPI router for geospatial file upload, inspection, and measurements."""

import logging
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status

from app.config import settings
from app.database import repo
from app.models.schemas import (
    FileListResponse,
    FileResponse,
    MeasurementResponse,
    MeasurementsListResponse,
)
from app.pipeline.graph import execute_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post(
    "/",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a geospatial file",
    description="Accepts a .zip containing a Shapefile or a .kml file. Extracts features and computes measurements.",
)
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    filename = file.filename or ""
    lower_name = filename.lower()

    if not (lower_name.endswith(".zip") or lower_name.endswith(".kml")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a .zip (Shapefile) or .kml file.",
        )

    # Prepare storage directory
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Initial file record
    temp_path = upload_dir / f"temp_{filename}"
    file_record = repo.create_file(filename=filename, file_path=str(temp_path))
    file_id = file_record["id"]

    # Target path using file_id to avoid collisions
    dest_path = upload_dir / f"{file_id}_{filename}"
    file_record = repo.update_file(file_id, status="PROCESSING")

    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        logger.exception("Failed to save uploaded file: %s", exc)
        repo.update_file(
            file_id,
            status="FAILED",
            error_message="Failed to write file to disk.",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error saving file.",
        )

    # Execute LangGraph pipeline
    try:
        execute_pipeline(
            file_id=file_id,
            filename=filename,
            file_path=str(dest_path),
        )
    except Exception as exc:
        logger.exception("Pipeline execution failed: %s", exc)
        repo.update_file(
            file_id,
            status="FAILED",
            error_message=f"Pipeline processing failed: {str(exc)}",
        )

    updated_record = repo.get_file(file_id)
    if not updated_record:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file record.",
        )

    return FileResponse(**updated_record)


@router.get(
    "/",
    response_model=FileListResponse,
    summary="List all uploaded files",
    description="Returns a list of all processed files.",
)
async def list_files():
    files = repo.list_files()
    return FileListResponse(files=[FileResponse(**f) for f in files])


@router.get(
    "/{file_id}/",
    response_model=FileResponse,
    summary="Get file information",
    description="Returns metadata and status for a specific uploaded file.",
)
async def get_file_info(file_id: str):
    file_record = repo.get_file(file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found.",
        )
    return FileResponse(**file_record)


@router.get(
    "/{file_id}/measurements/",
    response_model=MeasurementsListResponse,
    summary="Get file feature measurements",
    description="Returns detailed measurements for all extracted features.",
)
async def get_file_measurements(file_id: str):
    file_record = repo.get_file(file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found.",
        )

    measurements = repo.get_measurements(file_id)

    return MeasurementsListResponse(
        file_id=file_record["id"],
        filename=file_record["filename"],
        crs=file_record.get("crs"),
        feature_count=file_record.get("feature_count", 0),
        measurements=[MeasurementResponse(**m) for m in measurements],
    )
