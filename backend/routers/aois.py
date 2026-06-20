import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from shapely.geometry import shape
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, require_auth
from helios_common.geojson import aoi_feature, feature_collection
from schemas import AoiCreate

router = APIRouter(prefix="/aois", tags=["aois"])


def _polygon_wkt(geometry: dict) -> str:
    poly = shape(geometry)
    if poly.geom_type != "Polygon":
        raise HTTPException(status_code=400, detail="Only Polygon geometry supported")
    return poly.wkt


@router.get("")
async def list_aois(
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await session.execute(
        text(
            """
            SELECT id, name, priority::text, last_pass_at, monitoring_active,
                   ST_AsGeoJSON(polygon) AS geom
            FROM aois
            ORDER BY id
            """
        )
    )
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
            RETURNING id, name, priority::text, last_pass_at, monitoring_active,
                      ST_AsGeoJSON(polygon) AS geom
            """
        ),
        {"name": body.name, "priority": body.priority.value, "wkt": wkt},
    )
    await session.commit()
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create AOI")

    from helios_common.celery_app import celery_app

    celery_app.send_task(
        "scene_watcher.tasks.poll_aoi",
        args=[row["id"]],
        queue="scene_watch",
    )
    return aoi_feature(
        aoi_id=row["id"],
        polygon_geojson=json.loads(row["geom"]),
        name=row["name"],
        priority=row["priority"],
        last_pass_at=row["last_pass_at"],
        monitoring_active=row["monitoring_active"],
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
