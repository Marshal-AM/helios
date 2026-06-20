"""Shared SQL query helpers for API routers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from helios_common.geojson import detection_feature, feature_collection, parse_bbox


def _append_bbox(sql_parts: list[str], params: dict[str, Any], bbox: str | None) -> None:
    bounds = parse_bbox(bbox)
    if bounds is None:
        return
    min_lon, min_lat, max_lon, max_lat = bounds
    sql_parts.append(
        "AND ST_Intersects(d.bbox_polygon, ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326))"
    )
    params.update(
        {"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat}
    )


async def fetch_detections_geojson(
    session: AsyncSession,
    *,
    bbox: str | None = None,
    time_start: datetime | None = None,
    time_end: datetime | None = None,
    classes: list[str] | None = None,
    confidence_min: float | None = None,
    aoi_id: int | None = None,
) -> dict[str, Any]:
    sql = """
        SELECT d.id, d.lat, d.lon, d.class, d.subclass, d.confidence, d.heading_degrees,
               d.timestamp, d.scene_id, d.aoi_id, s.satellite_source,
               ST_AsGeoJSON(d.bbox_polygon) AS bbox_geojson
        FROM detections d
        JOIN scenes s ON s.id = d.scene_id
        WHERE 1=1
    """
    params: dict[str, Any] = {}
    parts = [sql]

    if aoi_id is not None:
        parts.append("AND d.aoi_id = :aoi_id")
        params["aoi_id"] = aoi_id
    if time_start is not None:
        parts.append("AND d.timestamp >= :time_start")
        params["time_start"] = time_start
    if time_end is not None:
        parts.append("AND d.timestamp <= :time_end")
        params["time_end"] = time_end
    if confidence_min is not None:
        parts.append("AND d.confidence >= :confidence_min")
        params["confidence_min"] = confidence_min
    if classes:
        parts.append("AND d.class = ANY(:classes)")
        params["classes"] = classes

    _append_bbox(parts, params, bbox)
    parts.append("ORDER BY d.timestamp DESC")
    query = "\n".join(parts)

    result = await session.execute(text(query), params)
    features = []
    for row in result.mappings():
        bbox_gj = json.loads(row["bbox_geojson"]) if row["bbox_geojson"] else None
        features.append(
            detection_feature(
                detection_id=row["id"],
                lat=row["lat"],
                lon=row["lon"],
                class_name=row["class"],
                confidence=row["confidence"],
                timestamp=row["timestamp"],
                subclass=row["subclass"],
                heading_degrees=row["heading_degrees"],
                scene_id=row["scene_id"],
                aoi_id=row["aoi_id"],
                satellite_source=row["satellite_source"],
                bbox_geojson=bbox_gj,
            )
        )
    return feature_collection(features)


async def fetch_detection_rows(
    session: AsyncSession,
    *,
    bbox: str | None = None,
    time_start: datetime | None = None,
    time_end: datetime | None = None,
    classes: list[str] | None = None,
    aoi_id: int | None = None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT d.id AS detection_id, d.class, d.subclass, d.confidence, d.lat, d.lon,
               d.heading_degrees, d.timestamp, s.satellite_source, a.name AS aoi_name
        FROM detections d
        JOIN scenes s ON s.id = d.scene_id
        JOIN aois a ON a.id = d.aoi_id
        WHERE 1=1
    """
    params: dict[str, Any] = {}
    parts = [sql]
    if aoi_id is not None:
        parts.append("AND d.aoi_id = :aoi_id")
        params["aoi_id"] = aoi_id
    if time_start is not None:
        parts.append("AND d.timestamp >= :time_start")
        params["time_start"] = time_start
    if time_end is not None:
        parts.append("AND d.timestamp <= :time_end")
        params["time_end"] = time_end
    if classes:
        parts.append("AND d.class = ANY(:classes)")
        params["classes"] = classes
    _append_bbox(parts, params, bbox)
    parts.append("ORDER BY d.timestamp DESC")
    result = await session.execute(text("\n".join(parts)), params)
    return [dict(r) for r in result.mappings()]
