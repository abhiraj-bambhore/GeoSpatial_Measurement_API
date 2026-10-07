from datetime import datetime

from pydantic import BaseModel, Field


class FileResponse(BaseModel):
    """Schema for file upload and detail responses."""

    id: str
    filename: str
    feature_count: int = 0
    crs: str | None = None
    status: str = "PENDING"
    error_message: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    """Schema for listing all uploaded files."""

    files: list[FileResponse]


class MeasurementResponse(BaseModel):
    """Schema for a single feature measurement."""

    id: str
    file_id: str
    feature_index: int
    geometry_type: str
    geometry_wkt: str | None = None
    properties: dict = Field(default_factory=dict)
    measurement_type: str | None = None
    measurement_value: float | None = None
    measurement_unit: str | None = None

    model_config = {"from_attributes": True}


class MeasurementsListResponse(BaseModel):
    """Schema for the measurements endpoint response."""

    file_id: str
    filename: str
    crs: str | None = None
    feature_count: int = 0
    measurements: list[MeasurementResponse]
