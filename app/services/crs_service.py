"""CRS detection, validation, and coordinate transformation.

Strategy: detect whether the source CRS is geographic (lat/lon).
If so, compute the UTM zone from the feature centroid and reproject
to that UTM CRS for accurate metric measurements.
"""

import logging
from functools import lru_cache

from pyproj import CRS, Transformer
from shapely.ops import transform as shapely_transform

logger = logging.getLogger(__name__)


def is_geographic_crs(crs_string: str) -> bool:
    """Return True if the CRS uses geographic (degree-based) coordinates."""
    try:
        crs = CRS.from_user_input(crs_string)
        return crs.is_geographic
    except Exception:
        logger.warning("Could not parse CRS '%s', assuming geographic.", crs_string)
        return True


def get_utm_epsg(lon: float, lat: float) -> int:
    """Calculate the EPSG code for the UTM zone covering a given point.

    Northern hemisphere: EPSG 326xx
    Southern hemisphere: EPSG 327xx
    """
    zone = int((lon + 180) / 6) + 1
    zone = max(1, min(zone, 60))
    if lat >= 0:
        return 32600 + zone
    return 32700 + zone


def get_projected_crs_for_geometry(geometry, source_crs: str) -> CRS:
    """Determine the best projected CRS for a geometry based on its centroid."""
    centroid = geometry.centroid
    epsg = get_utm_epsg(centroid.x, centroid.y)
    return CRS.from_epsg(epsg)


@lru_cache(maxsize=128)
def _get_transformer(source_crs_str: str, target_epsg: int) -> Transformer:
    """Return a cached Transformer between two coordinate reference systems."""
    return Transformer.from_crs(
        CRS.from_user_input(source_crs_str),
        CRS.from_epsg(target_epsg),
        always_xy=True,
    )


def transform_geometry(geometry, source_crs: str):
    """Transform a shapely geometry from source CRS to an appropriate projected CRS.

    Returns the reprojected geometry suitable for metric calculations.
    """
    target_crs = get_projected_crs_for_geometry(geometry, source_crs)
    target_epsg = target_crs.to_epsg()
    transformer = _get_transformer(source_crs, target_epsg)
    return shapely_transform(transformer.transform, geometry)


def format_crs(crs_obj) -> str:
    """Convert a fiona/pyproj CRS object to a human-readable string like EPSG:4326."""
    if crs_obj is None:
        return "UNKNOWN"

    try:
        proj_crs = CRS.from_user_input(crs_obj)
        epsg = proj_crs.to_epsg()
        if epsg:
            return f"EPSG:{epsg}"
        return proj_crs.to_wkt()
    except Exception:
        return str(crs_obj)
