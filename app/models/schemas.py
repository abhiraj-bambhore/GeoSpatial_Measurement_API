from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FileResponse(BaseModel):
    """Schema for file upload and detail responses."""

    id: str
    filename: str
    feature_count: int = 0
    crs: Optional[str] = None
    status: str = "PENDING"
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

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
    geometry_wkt: Optional[str] = None
    properties: dict = Field(default_factory=dict)
    measurement_type: Optional[str] = None
    measurement_value: Optional[float] = None
    measurement_unit: Optional[str] = None

    model_config = {"from_attributes": True}


class MeasurementsListResponse(BaseModel):
    """Schema for the measurements endpoint response."""

    file_id: str
    filename: str
    crs: Optional[str] = None
    feature_count: int = 0
    measurements: list[MeasurementResponse]
