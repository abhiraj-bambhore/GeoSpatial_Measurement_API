"""Integration and API tests for the Geospatial Measurement API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TEST_DATA_DIR = Path("tests/test_data")


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_invalid_file_extension():
    response = client.post(
        "/api/files/",
        files={"file": ("invalid.txt", b"plain text content", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_upload_and_measure_point_kml():
    file_path = TEST_DATA_DIR / "point.kml"
    assert file_path.exists(), "point.kml must exist"

    with open(file_path, "rb") as f:
        resp = client.post("/api/files/", files={"file": ("point.kml", f, "application/vnd.google-earth.kml+xml")})

    assert resp.status_code == 201
    data = resp.json()
    file_id = data["id"]
    assert data["filename"] == "point.kml"
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 1
    assert "4326" in data["crs"]

    # Verify GET /api/files/{id}/
    info_resp = client.get(f"/api/files/{file_id}/")
    assert info_resp.status_code == 200
    assert info_resp.json()["id"] == file_id

    # Verify GET /api/files/{id}/measurements/
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert len(meas_data["measurements"]) == 1
    feat = meas_data["measurements"][0]
    assert feat["geometry_type"] == "Point"
    assert feat["measurement_type"] == "none"
    assert feat["measurement_value"] is None
    assert feat["measurement_unit"] is None


def test_upload_and_measure_linestring_kml():
    file_path = TEST_DATA_DIR / "linestring.kml"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        resp = client.post("/api/files/", files={"file": ("linestring.kml", f, "application/vnd.google-earth.kml+xml")})

    assert resp.status_code == 201
    file_id = resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert len(meas_data["measurements"]) >= 1

    line_feat = next(m for m in meas_data["measurements"] if m["geometry_type"] == "LineString")
    assert line_feat["measurement_type"] == "length"
    assert line_feat["measurement_unit"] == "meters"
    assert line_feat["measurement_value"] > 0
    # Length in meters must be a realistic metric distance (> 500m), NOT degree units
    assert line_feat["measurement_value"] > 500


def test_upload_and_measure_polygon_kml():
    file_path = TEST_DATA_DIR / "polygon.kml"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        resp = client.post("/api/files/", files={"file": ("polygon.kml", f, "application/vnd.google-earth.kml+xml")})

    assert resp.status_code == 201
    file_id = resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert len(meas_data["measurements"]) >= 1

    poly_feat = next(m for m in meas_data["measurements"] if m["geometry_type"] == "Polygon")
    assert poly_feat["measurement_type"] == "area"
    assert poly_feat["measurement_unit"] == "sq_meters"
    assert poly_feat["measurement_value"] > 0
    # Area must be projected square meters, far greater than raw degree decimals
    assert poly_feat["measurement_value"] > 10_000


def test_upload_multiple_geometries_kml():
    file_path = TEST_DATA_DIR / "multiple_geometries.kml"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        resp = client.post("/api/files/", files={"file": ("multiple_geometries.kml", f, "application/vnd.google-earth.kml+xml")})

    assert resp.status_code == 201
    file_id = resp.json()["id"]
    assert resp.json()["feature_count"] == 3

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    items = meas_resp.json()["measurements"]

    types = {item["geometry_type"] for item in items}
    assert "Point" in types
    assert "LineString" in types
    assert "Polygon" in types


def test_upload_and_measure_shapefile_zip():
    file_path = TEST_DATA_DIR / "sample_shapefile.zip"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        resp = client.post("/api/files/", files={"file": ("sample_shapefile.zip", f, "application/zip")})

    assert resp.status_code == 201
    file_id = resp.json()["id"]
    assert resp.json()["status"] == "COMPLETED"
    assert resp.json()["feature_count"] == 2

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    measurements = meas_resp.json()["measurements"]
    assert len(measurements) == 2
    for m in measurements:
        assert m["geometry_type"] == "Polygon"
        assert m["measurement_type"] == "area"
        assert m["measurement_unit"] == "sq_meters"
        assert m["measurement_value"] > 0


def test_get_nonexistent_file():
    resp = client.get("/api/files/nonexistent-id-12345/")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_list_files_endpoint():
    resp = client.get("/api/files/")
    assert resp.status_code == 200
    assert "files" in resp.json()
    assert isinstance(resp.json()["files"], list)


def test_upload_natural_earth_countries_shapefile():
    file_path = TEST_DATA_DIR / "ne_50m_admin_0_countries.zip"
    if not file_path.exists():
        pytest.skip("Natural Earth dataset not downloaded")

    with open(file_path, "rb") as f:
        resp = client.post(
            "/api/files/",
            files={"file": ("ne_50m_admin_0_countries.zip", f, "application/zip")},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 241
    assert "4326" in data["crs"]

    # Verify measurements endpoint computes metric areas for all 241 countries
    file_id = data["id"]
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    measurements = meas_resp.json()["measurements"]
    assert len(measurements) == 241
    assert measurements[0]["geometry_type"] in ("Polygon", "MultiPolygon")
    assert measurements[0]["measurement_type"] == "area"
    assert measurements[0]["measurement_unit"] == "sq_meters"
    assert measurements[0]["measurement_value"] > 1_000_000

