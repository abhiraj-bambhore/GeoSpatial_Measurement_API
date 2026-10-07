"""Pytest fixtures for generating sample KML and Shapefile (.zip) test files."""

import io
import tempfile
import zipfile
from pathlib import Path

import fiona
import pytest
from fiona.crs import from_epsg
from shapely.geometry import LineString, Point, Polygon, mapping


@pytest.fixture
def sample_kml_content() -> str:
    """Return a standard KML document with Polygon, LineString, and Point."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Sample Geospatial Survey</name>
    <Placemark>
      <name>Survey Polygon</name>
      <description>Sample parcel boundary</description>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5900,12.9700,0
              77.6000,12.9700,0
              77.6000,12.9800,0
              77.5900,12.9800,0
              77.5900,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Survey Line</name>
      <description>Sample road centerline</description>
      <LineString>
        <coordinates>
          77.5900,12.9700,0
          77.5950,12.9750,0
          77.6000,12.9800,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Survey Point</name>
      <description>Sample benchmark location</description>
      <Point>
        <coordinates>77.5945,12.9716,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""


@pytest.fixture
def sample_kml_file(sample_kml_content, tmp_path) -> Path:
    kml_path = tmp_path / "survey.kml"
    kml_path.write_text(sample_kml_content, encoding="utf-8")
    return kml_path


@pytest.fixture
def sample_shapefile_zip(tmp_path) -> Path:
    """Create a temporary Shapefile and package it into a .zip archive."""
    shp_dir = tmp_path / "shp_temp"
    shp_dir.mkdir(parents=True, exist_ok=True)
    shp_file = shp_dir / "parcels.shp"

    schema = {
        "geometry": "Polygon",
        "properties": {"name": "str:50", "zone": "str:20"},
    }

    crs = from_epsg(4326)

    # Polygon roughly in Bengaluru, India
    poly = Polygon(
        [
            (77.5900, 12.9700),
            (77.6000, 12.9700),
            (77.6000, 12.9800),
            (77.5900, 12.9800),
            (77.5900, 12.9700),
        ]
    )

    with fiona.open(
        str(shp_file),
        mode="w",
        driver="ESRI Shapefile",
        schema=schema,
        crs=crs,
    ) as layer:
        layer.write(
            {
                "geometry": mapping(poly),
                "properties": {"name": "Downtown Parcel", "zone": "Commercial"},
            }
        )

    zip_path = tmp_path / "parcels.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for ext in [".shp", ".shx", ".dbf", ".prj"]:
            f = shp_dir / f"parcels{ext}"
            if f.exists():
                zf.write(f, arcname=f.name)

    return zip_path
