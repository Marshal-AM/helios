import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from shapely.geometry import shape
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, require_auth
from helios_common.geojson import aoi_feature, feature_collection
from schemas import AoiCreate, AoiUpdate

router = APIRouter(prefix="/aois", tags=["aois"])


def _polygon_wkt(geometry: dict) -> str:
    poly = shape(geometry)
    if poly.geom_type != "Polygon":
        raise HTTPException(status_code=400, detail="Only Polygon geometry supported")
    return poly.wkt


_AOI_SELECT = """
    SELECT a.id, a.name, a.priority::text, a.last_pass_at, a.monitoring_active,
           ST_AsGeoJSON(a.polygon) AS geom,
           ls.satellite_source AS last_satellite_source,
           ls.cloud_cover_pct AS last_cloud_cover_pct,
           COALESCE(dc.cnt, 0) AS active_detection_count
    FROM aois a
    LEFT JOIN LATERAL (
        SELECT satellite_source, cloud_cover_pct
        FROM scenes
        WHERE aoi_id = a.id
        ORDER BY acquisition_timestamp DESC
        LIMIT 1
    ) ls ON true
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::int AS cnt
        FROM detections
        WHERE aoi_id = a.id
          AND timestamp >= NOW() - INTERVAL '7 days'
    ) dc ON true
"""


@router.get("")
async def list_aois(
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await session.execute(text(f"{_AOI_SELECT} ORDER BY a.id"))
    features = []
    for row in result.mappings():
        features.append(
            aoi_feature(
                aoi_id=row["id"],
                polygon_geojson=json.loads(row["geom"]),
                name=row["name"],
                priority=row["priority"],
                last_pass_at=row["last_pass_at"],
                monitoring_active=row["monitoring_active"],
                last_satellite_source=row["last_satellite_source"],
                last_cloud_cover_pct=row["last_cloud_cover_pct"],
                active_detection_count=row["active_detection_count"] or 0,
            )
        )
    return feature_collection(features)


@router.post("", status_code=201)
async def create_aoi(
    body: AoiCreate,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    wkt = _polygon_wkt(body.geometry.model_dump())
    result = await session.execute(
        text(
            """
            INSERT INTO aois (name, priority, polygon, monitoring_active)
            VALUES (:name, :priority, ST_GeomFromText(:wkt, 4326), true)
            RETURNING id
            """
        ),
        {"name": body.name, "priority": body.priority.value, "wkt": wkt},
    )
    await session.commit()
    aoi_id = result.scalar()
    if not aoi_id:
        raise HTTPException(status_code=500, detail="Failed to create AOI")

    from helios_common.celery_app import celery_app

    celery_app.send_task(
        "scene_watcher.tasks.poll_aoi",
        args=[aoi_id],
        queue="scene_watch",
    )

    row = (
        await session.execute(
            text(f"{_AOI_SELECT} WHERE a.id = :id"),
            {"id": aoi_id},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=500, detail="Failed to load created AOI")
    return aoi_feature(
        aoi_id=row["id"],
        polygon_geojson=json.loads(row["geom"]),
        name=row["name"],
        priority=row["priority"],
        last_pass_at=row["last_pass_at"],
        monitoring_active=row["monitoring_active"],
        last_satellite_source=row["last_satellite_source"],
        last_cloud_cover_pct=row["last_cloud_cover_pct"],
        active_detection_count=row["active_detection_count"] or 0,
    )


@router.patch("/{aoi_id}")
async def update_aoi(
    aoi_id: int,
    body: AoiUpdate,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    if body.monitoring_active is None and body.priority is None:
        raise HTTPException(status_code=400, detail="No fields to update")

    sets: list[str] = []
    params: dict = {"id": aoi_id}
    if body.monitoring_active is not None:
        sets.append("monitoring_active = :monitoring_active")
        params["monitoring_active"] = body.monitoring_active
    if body.priority is not None:
        sets.append("priority = :priority")
        params["priority"] = body.priority.value

    result = await session.execute(
        text(f"UPDATE aois SET {', '.join(sets)} WHERE id = :id RETURNING id"),
        params,
    )
    await session.commit()
    if not result.first():
        raise HTTPException(status_code=404, detail="AOI not found")

    row = (
        await session.execute(
            text(f"{_AOI_SELECT} WHERE a.id = :id"),
            {"id": aoi_id},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="AOI not found")
    return aoi_feature(
        aoi_id=row["id"],
        polygon_geojson=json.loads(row["geom"]),
        name=row["name"],
        priority=row["priority"],
        last_pass_at=row["last_pass_at"],
        monitoring_active=row["monitoring_active"],
        last_satellite_source=row["last_satellite_source"],
        last_cloud_cover_pct=row["last_cloud_cover_pct"],
        active_detection_count=row["active_detection_count"] or 0,
    )


@router.delete("/{aoi_id}")
async def deactivate_aoi(
    aoi_id: int,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await session.execute(
        text(
            """
            UPDATE aois SET monitoring_active = false WHERE id = :id
            RETURNING id
            """
        ),
        {"id": aoi_id},
    )
    await session.commit()
    if not result.first():
        raise HTTPException(status_code=404, detail="AOI not found")
    return {"id": aoi_id, "monitoring_active": False}
