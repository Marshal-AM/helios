from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, require_auth

router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.get("")
async def list_scenes(
    aoi_id: int | None = Query(None),
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    sql = """
        SELECT id, aoi_id, satellite_source, external_scene_id, sensor_type,
               acquisition_timestamp, cloud_cover_pct, scene_path, processed, created_at
        FROM scenes
        WHERE 1=1
    """
    params: dict = {}
    parts = [sql]
    if aoi_id is not None:
        parts.append("AND aoi_id = :aoi_id")
        params["aoi_id"] = aoi_id
    parts.append("ORDER BY acquisition_timestamp DESC")
    result = await session.execute(text("\n".join(parts)), params)
    scenes = []
    for row in result.mappings():
        scenes.append(
            {
                "id": row["id"],
                "aoi_id": row["aoi_id"],
                "satellite_source": row["satellite_source"],
                "external_scene_id": row["external_scene_id"],
                "sensor_type": row["sensor_type"],
                "acquisition_timestamp": (
                    row["acquisition_timestamp"].isoformat() if row["acquisition_timestamp"] else None
                ),
                "cloud_cover_pct": row["cloud_cover_pct"],
                "scene_path": row["scene_path"],
                "processed": row["processed"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )
    return {"scenes": scenes}
