from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, require_auth

router = APIRouter(prefix="/changes", tags=["changes"])


@router.get("")
async def list_changes(
    aoi_id: int | None = Query(None),
    time_start: datetime | None = Query(None),
    time_end: datetime | None = Query(None),
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    sql = """
        SELECT ce.id, ce.aoi_id, ce.event_type::text, ce.distance_moved_m, ce.speed_kmh,
               ce.bearing_degrees, ce.timestamp, ce.alert_fired,
               d1.lat AS t1_lat, d1.lon AS t1_lon, d1.class AS t1_class,
               d2.lat AS t2_lat, d2.lon AS t2_lon, d2.class AS t2_class
        FROM change_events ce
        LEFT JOIN detections d1 ON d1.id = ce.detection_id_t1
        LEFT JOIN detections d2 ON d2.id = ce.detection_id_t2
        WHERE 1=1
    """
    params: dict = {}
    parts = [sql]
    if aoi_id is not None:
        parts.append("AND ce.aoi_id = :aoi_id")
        params["aoi_id"] = aoi_id
    if time_start is not None:
        parts.append("AND ce.timestamp >= :time_start")
        params["time_start"] = time_start
    if time_end is not None:
        parts.append("AND ce.timestamp <= :time_end")
        params["time_end"] = time_end
    parts.append("ORDER BY ce.timestamp DESC")
    result = await session.execute(text("\n".join(parts)), params)
    events = []
    for row in result.mappings():
        events.append(
            {
                "id": row["id"],
                "aoi_id": row["aoi_id"],
                "event_type": row["event_type"],
                "distance_moved_m": row["distance_moved_m"],
                "speed_kmh": row["speed_kmh"],
                "bearing_degrees": row["bearing_degrees"],
                "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                "alert_fired": row["alert_fired"],
                "t1": (
                    {"lat": row["t1_lat"], "lon": row["t1_lon"], "class": row["t1_class"]}
                    if row["t1_lat"] is not None
                    else None
                ),
                "t2": (
                    {"lat": row["t2_lat"], "lon": row["t2_lon"], "class": row["t2_class"]}
                    if row["t2_lat"] is not None
                    else None
                ),
            }
        )
    return {"events": events}
