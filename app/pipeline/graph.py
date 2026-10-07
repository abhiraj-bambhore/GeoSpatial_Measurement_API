"""Production LangGraph workflow for Geospatial File Processing and Measurement.

Orchestrates the entire geospatial lifecycle:
1. Validation: Checks file existence, format (.zip / .kml), and constraints.
2. Extraction: Reads layers and features, extracts WKT, properties, and CRS.
3. Measurement & CRS Transformation: Auto-projects geographic coordinates (e.g. EPSG:4326)
   to appropriate local UTM projection; computes Polygon Area (m²), LineString Length (m),
   and handles Points and unsupported geometries gracefully.
4. Persistence: Saves records and measurements to the database repository.
5. Error Handling: Catches and records failures gracefully without system crashes.
"""

import logging
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.database import repo
from app.services.crs_service import (
    is_geographic_crs,
    transform_geometry,
)
from app.services.geo_service import MEASUREMENT_MAP, read_geospatial_file

logger = logging.getLogger(__name__)


class ProcessingState(TypedDict):
    file_id: str
    filename: str
    file_path: str
    is_valid: bool
    status: str
    error: str | None
    crs: str | None
    features: list[dict[str, Any]]
    measurements: list[dict[str, Any]]


def validate_input(state: ProcessingState) -> dict[str, Any]:
    """Validate file path, extension, and integrity."""
    file_path = Path(state["file_path"])
    filename = state["filename"].lower()

    if not file_path.exists():
        return {
            "is_valid": False,
            "error": f"File does not exist on disk: {state['file_path']}",
            "status": "FAILED",
        }

    if not filename.endswith((".zip", ".kml")):
        return {
            "is_valid": False,
            "error": "Unsupported file format. Only .zip (Shapefile) or .kml files are accepted.",
            "status": "FAILED",
        }

    return {"is_valid": True, "status": "PROCESSING", "error": None}


def extract_features(state: ProcessingState) -> dict[str, Any]:
    """Extract geospatial features and source CRS from the file."""
    try:
        features, crs_string = read_geospatial_file(
            state["file_path"], state["filename"]
        )
        return {
            "features": features,
            "crs": crs_string,
            "status": "PROCESSING",
        }
    except Exception as exc:
        logger.exception("Feature extraction error")
        return {
            "is_valid": False,
            "error": f"Failed to extract geospatial features: {exc!s}",
            "status": "FAILED",
        }


def calculate_measurements(state: ProcessingState) -> dict[str, Any]:
    """Calculate measurements with robust CRS reprojection."""
    features = state.get("features", [])
    source_crs = state.get("crs") or "EPSG:4326"
    measurements: list[dict[str, Any]] = []

    from shapely import wkt as shapely_wkt

    is_geo = is_geographic_crs(source_crs)

    for feat in features:
        geom_type = feat.get("geometry_type", "Unknown")
        wkt_str = feat.get("geometry_wkt")
        meas_type = MEASUREMENT_MAP.get(geom_type, "unsupported")

        item: dict[str, Any] = {
            "feature_index": feat["index"],
            "geometry_type": geom_type,
            "geometry_wkt": wkt_str,
            "properties": feat.get("properties", {}),
            "measurement_type": meas_type,
            "measurement_value": None,
            "measurement_unit": None,
        }

        if meas_type in ("none", "unsupported") or not wkt_str:
            measurements.append(item)
            continue

        try:
            geom = shapely_wkt.loads(wkt_str)
            projected_geom = geom

            # If coordinates are in geographic degrees (lat/lon), reproject to metric UTM zone
            if is_geo:
                projected_geom = transform_geometry(geom, source_crs)

            if meas_type == "area":
                item["measurement_value"] = round(projected_geom.area, 4)
                item["measurement_unit"] = "sq_meters"
            elif meas_type == "length":
                item["measurement_value"] = round(projected_geom.length, 4)
                item["measurement_unit"] = "meters"

        except Exception as exc:
            logger.warning(
                "Measurement calculation error for feature index %s: %s",
                feat["index"],
                exc,
            )
            item["measurement_type"] = "error"
            item["measurement_value"] = None

        measurements.append(item)

    return {"measurements": measurements, "status": "COMPLETED"}


def persist_results(state: ProcessingState) -> dict[str, Any]:
    """Persist final metadata and feature measurements to the database repository."""
    file_id = state["file_id"]
    feature_count = len(state.get("features", []))
    crs_str = state.get("crs")
    measurements = state.get("measurements", [])

    repo.update_file(
        file_id,
        status="COMPLETED",
        feature_count=feature_count,
        crs=crs_str,
    )
    repo.save_measurements(file_id, measurements)

    logger.info("Successfully processed file %s with %d features", file_id, feature_count)
    return {"status": "COMPLETED"}


def handle_error(state: ProcessingState) -> dict[str, Any]:
    """Handle and log pipeline failure states."""
    file_id = state["file_id"]
    error_msg = state.get("error") or "Unknown processing error occurred."

    repo.update_file(
        file_id,
        status="FAILED",
        error_message=error_msg,
    )
    logger.error("Processing failed for file %s: %s", file_id, error_msg)
    return {"status": "FAILED"}


def route_after_validation(state: ProcessingState) -> str:
    if not state.get("is_valid", True):
        return "handle_error"
    return "extract_features"


def route_after_extraction(state: ProcessingState) -> str:
    if not state.get("is_valid", True) or state.get("error"):
        return "handle_error"
    return "calculate_measurements"


def build_geospatial_pipeline():
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(ProcessingState)

    workflow.add_node("validate_input", validate_input)
    workflow.add_node("extract_features", extract_features)
    workflow.add_node("calculate_measurements", calculate_measurements)
    workflow.add_node("persist_results", persist_results)
    workflow.add_node("handle_error", handle_error)

    workflow.set_entry_point("validate_input")

    workflow.add_conditional_edges(
        "validate_input",
        route_after_validation,
        {
            "extract_features": "extract_features",
            "handle_error": "handle_error",
        },
    )

    workflow.add_conditional_edges(
        "extract_features",
        route_after_extraction,
        {
            "calculate_measurements": "calculate_measurements",
            "handle_error": "handle_error",
        },
    )

    workflow.add_edge("calculate_measurements", "persist_results")
    workflow.add_edge("persist_results", END)
    workflow.add_edge("handle_error", END)

    return workflow.compile()


geospatial_pipeline = build_geospatial_pipeline()


def execute_pipeline(file_id: str, filename: str, file_path: str) -> dict[str, Any]:
    """Execute the LangGraph processing workflow synchronously or in background."""
    initial_state: ProcessingState = {
        "file_id": file_id,
        "filename": filename,
        "file_path": file_path,
        "is_valid": True,
        "status": "PENDING",
        "error": None,
        "crs": None,
        "features": [],
        "measurements": [],
    }
    return geospatial_pipeline.invoke(initial_state)
