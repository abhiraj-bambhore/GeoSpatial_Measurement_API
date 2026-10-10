"""Seed pre-packaged geospatial datasets for diverse geometry testing."""

import logging
from pathlib import Path
from typing import Any

from app.database import repo
from app.pipeline.graph import execute_pipeline

logger = logging.getLogger(__name__)

SAMPLE_FILES: list[tuple[str, str]] = [
    ("sample_shapefile.zip", "sample_shapefile.zip"),
    ("polygon_reservoir.kml", "polygon.kml"),
    ("linestring_shoreline.kml", "linestring.kml"),
    ("multiple_geometries.kml", "multiple_geometries.kml"),
    ("point_landmark.kml", "point.kml"),
    ("national_park_boundary.kml", "national_park_boundary.kml"),
    ("flight_path_corridor.kml", "flight_path_corridor.kml"),
    ("city_metro_stations.kml", "city_metro_stations.kml"),
    ("solar_farm_parcels.kml", "solar_farm_parcels.kml"),
    ("airport_runways_complex.kml", "airport_runways_complex.kml"),
]


def seed_sample_datasets() -> list[dict[str, Any]]:
    """Seed sample geospatial files covering Polygon, LineString, Point, and Shapefile."""
    samples_dir = Path(__file__).parent
    existing_records = repo.list_files()
    existing_filenames = {f.get("filename") for f in existing_records}

    seeded_files: list[dict[str, Any]] = []

    for display_name, source_filename in SAMPLE_FILES:
        if display_name in existing_filenames:
            continue

        source_path = samples_dir / source_filename
        if not source_path.exists():
            continue

        try:
            record = repo.create_file(filename=display_name, file_path=str(source_path))
            file_id = record["id"]
            repo.update_file(file_id, status="PROCESSING")
            execute_pipeline(file_id=file_id, filename=display_name, file_path=str(source_path))
            seeded_files.append(record)
            logger.info("Successfully seeded dataset: %s (%s)", display_name, file_id)
        except Exception as exc:
            logger.warning("Failed to seed sample dataset %s: %s", display_name, exc)

    return seeded_files
