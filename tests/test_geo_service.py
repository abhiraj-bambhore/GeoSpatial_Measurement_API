"""Unit tests for CRS service and geospatial measurement calculation."""

import pytest
from shapely.geometry import LineString, Point, Polygon

from app.services.crs_service import (
    get_utm_epsg,
    is_geographic_crs,
    transform_geometry,
)
from app.services.geo_service import compute_measurement, read_geospatial_file


def test_utm_epsg_calculation():
    # Bengaluru: lon ~77.59, lat ~12.97 -> UTM zone 43N (EPSG 32643)
    assert get_utm_epsg(77.59, 12.97) == 32643

    # New York: lon -74.00, lat 40.71 -> UTM zone 18N (EPSG 32618)
    assert get_utm_epsg(-74.00, 40.71) == 32618

    # Sydney: lon 151.20, lat -33.86 -> UTM zone 56S (EPSG 32756)
    assert get_utm_epsg(151.20, -33.86) == 32756


def test_is_geographic_crs():
    assert is_geographic_crs("EPSG:4326") is True
    assert is_geographic_crs("EPSG:3857") is False
    assert is_geographic_crs("EPSG:32643") is False


def test_polygon_area_measurement_reprojected():
    # Polygon around ~0.01 deg lat by 0.01 deg lon (~1.1 km by 1.08 km)
    # Degrees area is 0.0001 (which would be completely wrong without reprojection)
    # Reprojected area should be roughly ~1,200,000 square meters
    poly = Polygon([(77.59, 12.97), (77.60, 12.97), (77.60, 12.98), (77.59, 12.98), (77.59, 12.97)])
    feature = {
        "index": 0,
        "geometry_type": "Polygon",
        "geometry_wkt": poly.wkt,
        "properties": {"name": "Test Parcel"},
    }

    result = compute_measurement(feature, source_crs="EPSG:4326")

    assert result["measurement_type"] == "area"
    assert result["measurement_unit"] == "sq_meters"
    assert result["measurement_value"] is not None
    # Verify the value is in square meters (metric scale), definitely > 500,000 m²
    assert result["measurement_value"] > 500_000
    # Must NOT be 0.0001 (which would mean it was computed in raw degrees)
    assert result["measurement_value"] != pytest.approx(0.0001)


def test_linestring_length_measurement_reprojected():
    line = LineString([(77.59, 12.97), (77.60, 12.98)])
    feature = {
        "index": 1,
        "geometry_type": "LineString",
        "geometry_wkt": line.wkt,
        "properties": {"name": "Test Highway"},
    }

    result = compute_measurement(feature, source_crs="EPSG:4326")

    assert result["measurement_type"] == "length"
    assert result["measurement_unit"] == "meters"
    assert result["measurement_value"] is not None
    # Roughly ~1.5 km line
    assert result["measurement_value"] > 1000


def test_point_measurement_none():
    pt = Point(77.59, 12.97)
    feature = {
        "index": 2,
        "geometry_type": "Point",
        "geometry_wkt": pt.wkt,
        "properties": {"name": "Benchmark"},
    }

    result = compute_measurement(feature, source_crs="EPSG:4326")

    assert result["measurement_type"] == "none"
    assert result["measurement_unit"] is None
    assert result["measurement_value"] is None


def test_unsupported_geometry_graceful_handling():
    feature = {
        "index": 3,
        "geometry_type": "GeometryCollection",
        "geometry_wkt": "GEOMETRYCOLLECTION (POINT (10 10), LINESTRING (10 10, 20 20))",
        "properties": {},
    }

    result = compute_measurement(feature, source_crs="EPSG:4326")

    assert result["measurement_type"] == "unsupported"
    assert result["measurement_value"] is None
    assert result["measurement_unit"] is None
