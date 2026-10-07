"""Geospatial file reading and measurement computation.

Reads Shapefiles (.zip) and KML files using fiona/OGR with native XML fallback.
Computes area (Polygon), length (LineString), or marks unsupported types.
"""

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

import fiona
from shapely import wkt as shapely_wkt
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon, shape

from app.services.crs_service import format_crs, is_geographic_crs, transform_geometry

logger = logging.getLogger(__name__)

MEASUREMENT_MAP: dict[str, str] = {
    "Point": "none",
    "MultiPoint": "none",
    "LineString": "length",
    "MultiLineString": "length",
    "Polygon": "area",
    "MultiPolygon": "area",
}


def _strip_ns(tag: str) -> str:
    """Strip XML namespace prefix from a tag name."""
    return re.sub(r"\{.*?\}", "", tag)


def _parse_coordinates(coord_text: str) -> list[tuple[float, float]]:
    """Parse KML coordinate tuples: 'lon,lat,alt lon,lat,alt ...'"""
    coords: list[tuple[float, float]] = []
    if not coord_text:
        return coords

    tokens = coord_text.strip().split()
    for token in tokens:
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                coords.append((lon, lat))
            except ValueError:
                continue
    return coords


def _parse_kml_native(file_path: str) -> list[dict[str, Any]]:
    """Parse KML file using standard library ElementTree.

    Guarantees cross-platform reliability without depending on GDAL/Expat KML drivers.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    features: list[dict[str, Any]] = []

    # Find all Placemark elements regardless of namespace
    for elem in root.iter():
        if _strip_ns(elem.tag) != "Placemark":
            continue

        props: dict[str, Any] = {}
        geometries = []

        for child in elem:
            tag_name = _strip_ns(child.tag)
            if tag_name in ("name", "description"):
                if child.text:
                    props[tag_name] = child.text.strip()
            elif tag_name == "ExtendedData":
                for data_node in child.iter():
                    if _strip_ns(data_node.tag) in ("Data", "SimpleData"):
                        key = data_node.get("name")
                        val = data_node.text
                        if key and val:
                            props[key] = val.strip()

        def extract_geometries_from_node(node):
            node_tag = _strip_ns(node.tag)
            if node_tag == "Point":
                coord_elem = next((c for c in node if _strip_ns(c.tag) == "coordinates"), None)
                if coord_elem is not None and coord_elem.text:
                    coords = _parse_coordinates(coord_elem.text)
                    if coords:
                        geometries.append(Point(coords[0]))
            elif node_tag == "LineString":
                coord_elem = next((c for c in node if _strip_ns(c.tag) == "coordinates"), None)
                if coord_elem is not None and coord_elem.text:
                    coords = _parse_coordinates(coord_elem.text)
                    if len(coords) >= 2:
                        geometries.append(LineString(coords))
            elif node_tag == "Polygon":
                shell_coords = []
                holes = []
                for poly_child in node:
                    child_tag = _strip_ns(poly_child.tag)
                    if child_tag == "outerBoundaryIs":
                        for ring in poly_child:
                            if _strip_ns(ring.tag) == "LinearRing":
                                crd = next((c for c in ring if _strip_ns(c.tag) == "coordinates"), None)
                                if crd is not None and crd.text:
                                    shell_coords = _parse_coordinates(crd.text)
                    elif child_tag == "innerBoundaryIs":
                        for ring in poly_child:
                            if _strip_ns(ring.tag) == "LinearRing":
                                crd = next((c for c in ring if _strip_ns(c.tag) == "coordinates"), None)
                                if crd is not None and crd.text:
                                    h_coords = _parse_coordinates(crd.text)
                                    if len(h_coords) >= 3:
                                        holes.append(h_coords)
                if len(shell_coords) >= 3:
                    geometries.append(Polygon(shell_coords, holes))
            elif node_tag == "MultiGeometry":
                for sub in node:
                    extract_geometries_from_node(sub)

        for child in elem:
            extract_geometries_from_node(child)

        for geom in geometries:
            features.append(
                {
                    "index": len(features),
                    "geometry_type": geom.geom_type,
                    "geometry_wkt": geom.wkt,
                    "properties": dict(props),
                }
            )

    return features


def read_geospatial_file(
    file_path: str, filename: str
) -> tuple[list[dict], str]:
    """Read a geospatial file and extract all features.

    Args:
        file_path: Absolute path to the file on disk.
        filename: Original filename (used to determine format).

    Returns:
        Tuple of (features_list, crs_string).
    """
    ext = Path(filename).suffix.lower()

    if ext == ".kml":
        # First attempt native robust KML XML parser
        try:
            features = _parse_kml_native(file_path)
            return features, "EPSG:4326"
        except Exception as exc:
            logger.warning("Native KML parser failed (%s), attempting Fiona...", exc)

    if ext == ".zip":
        source = f"zip://{file_path}"
        open_kwargs: dict = {}
    elif ext == ".kml":
        source = file_path
        open_kwargs = {"driver": "KML"}
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    features = []
    crs_string: Optional[str] = None

    try:
        layer_names = fiona.listlayers(source)
    except Exception:
        layer_names = [None]

    for layer_name in layer_names:
        kw = dict(open_kwargs)
        if layer_name is not None:
            kw["layer"] = layer_name

        try:
            with fiona.open(source, **kw) as src:
                if crs_string is None and src.crs:
                    crs_string = format_crs(src.crs)

                for feature in src:
                    geom_data = feature.get("geometry")
                    if geom_data is None:
                        continue

                    geom = shape(geom_data)
                    properties = dict(feature.get("properties", {}) or {})

                    features.append(
                        {
                            "index": len(features),
                            "geometry_type": geom.geom_type,
                            "geometry_wkt": geom.wkt,
                            "properties": properties,
                        }
                    )
        except Exception as exc:
            logger.warning(
                "Failed to read layer '%s' from '%s': %s",
                layer_name,
                filename,
                exc,
            )

    if crs_string is None and ext == ".kml":
        crs_string = "EPSG:4326"

    return features, crs_string or "UNKNOWN"


def compute_measurement(feature: dict, source_crs: Optional[str]) -> dict:
    """Compute the measurement for a single feature.

    Args:
        feature: Dict with index, geometry_type, geometry_wkt, properties.
        source_crs: Source CRS string (e.g. "EPSG:4326").

    Returns:
        Dict with measurement details ready for database insertion.
    """
    geom = shapely_wkt.loads(feature["geometry_wkt"])
    geom_type = geom.geom_type
    measurement_type = MEASUREMENT_MAP.get(geom_type, "unsupported")

    result = {
        "feature_index": feature["index"],
        "geometry_type": geom_type,
        "geometry_wkt": feature["geometry_wkt"],
        "properties": feature.get("properties", {}),
        "measurement_type": measurement_type,
        "measurement_value": None,
        "measurement_unit": None,
    }

    if measurement_type in ("none", "unsupported"):
        return result

    # Reproject to a metric CRS if the source is geographic
    projected_geom = geom
    if source_crs and source_crs != "UNKNOWN" and is_geographic_crs(source_crs):
        projected_geom = transform_geometry(geom, source_crs)

    if measurement_type == "area":
        result["measurement_value"] = round(projected_geom.area, 4)
        result["measurement_unit"] = "sq_meters"
    elif measurement_type == "length":
        result["measurement_value"] = round(projected_geom.length, 4)
        result["measurement_unit"] = "meters"

    return result
