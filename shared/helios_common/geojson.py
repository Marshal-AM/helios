"""GeoJSON helpers for Helios API responses."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    """Parse 'minLon,minLat,maxLon,maxLat' into WGS84 bounds."""
    if not bbox:
        return None
    parts = [float(p.strip()) for p in bbox.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be minLon,minLat,maxLon,maxLat")
    return parts[0], parts[1], parts[2], parts[3]


def feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def point_feature(
    lon: float,
    lat: float,
    properties: dict[str, Any],
    feature_id: int | str | None = None,
) -> dict[str, Any]:
    feat: dict[str, Any] = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties,
    }
    if feature_id is not None:
        feat["id"] = feature_id
    return feat


def polygon_feature(
    geojson_geometry: dict[str, Any] | str,
    properties: dict[str, Any],
    feature_id: int | str | None = None,
) -> dict[str, Any]:
    if isinstance(geojson_geometry, str):
        geojson_geometry = json.loads(geojson_geometry)
    feat: dict[str, Any] = {
        "type": "Feature",
        "geometry": geojson_geometry,
        "properties": properties,
    }
    if feature_id is not None:
        feat["id"] = feature_id
    return feat


def detection_feature(
    detection_id: int,
    lat: float,
    lon: float,
    class_name: str,
    confidence: float,
    timestamp: datetime,
    *,
    subclass: str | None = None,
    heading_degrees: float | None = None,
    scene_id: int | None = None,
    aoi_id: int | None = None,
    satellite_source: str | None = None,
    bbox_geojson: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    props: dict[str, Any] = {
        "detection_id": detection_id,
        "class": class_name,
        "subclass": subclass,
        "confidence": confidence,
        "lat": lat,
        "lon": lon,
        "heading_degrees": heading_degrees,
        "timestamp": timestamp.isoformat() if timestamp else None,
        "scene_id": scene_id,
        "aoi_id": aoi_id,
        "satellite_source": satellite_source,
    }
    if bbox_geojson is not None:
        if isinstance(bbox_geojson, str):
            bbox_geojson = json.loads(bbox_geojson)
        return {
            "type": "Feature",
            "id": detection_id,
            "geometry": bbox_geojson,
            "properties": props,
        }
    return point_feature(lon, lat, props, feature_id=detection_id)


def aoi_feature(
    aoi_id: int,
    polygon_geojson: dict[str, Any] | str,
    name: str,
    priority: str,
    last_pass_at: datetime | None,
    monitoring_active: bool,
    *,
    last_satellite_source: str | None = None,
    last_cloud_cover_pct: float | None = None,
    active_detection_count: int = 0,
) -> dict[str, Any]:
    return polygon_feature(
        polygon_geojson,
        {
            "aoi_id": aoi_id,
            "name": name,
            "priority": priority,
            "last_pass_at": last_pass_at.isoformat() if last_pass_at else None,
            "monitoring_active": monitoring_active,
            "last_satellite_source": last_satellite_source,
            "last_cloud_cover_pct": last_cloud_cover_pct,
            "active_detection_count": active_detection_count,
        },
        feature_id=aoi_id,
    )
