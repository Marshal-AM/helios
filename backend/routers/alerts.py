from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, require_auth
from helios_common.models import AlertSeverity
from schemas import AlertAcknowledge

router = APIRouter(prefix="/alerts", tags=["alerts"])

_SEVERITY_ORDER = """
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        ELSE 4
    END
"""


@router.get("")
async def list_alerts(
    aoi_id: int | None = Query(None),
    severity: AlertSeverity | None = Query(None),
    acknowledged: bool | None = Query(None),
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    sql = """
        SELECT a.id, a.aoi_id, a.change_event_id, a.alert_type, a.severity::text,
               a.lat, a.lon, a.description, a.acknowledged, a.acknowledged_by,
               a.timestamp, ao.name AS aoi_name
        FROM alerts a
        JOIN aois ao ON ao.id = a.aoi_id
        WHERE 1=1
    """
    params: dict = {}
    parts = [sql]
    if aoi_id is not None:
        parts.append("AND a.aoi_id = :aoi_id")
        params["aoi_id"] = aoi_id
    if severity is not None:
        parts.append("AND a.severity = :severity")
        params["severity"] = severity.value
    if acknowledged is not None:
        parts.append("AND a.acknowledged = :acknowledged")
        params["acknowledged"] = acknowledged
    parts.append(f"ORDER BY {_SEVERITY_ORDER}, a.timestamp DESC")
    result = await session.execute(text("\n".join(parts)), params)
    alerts = []
    for row in result.mappings():
        alerts.append(
            {
                "id": row["id"],
                "aoi_id": row["aoi_id"],
                "aoi_name": row["aoi_name"],
                "change_event_id": row["change_event_id"],
                "alert_type": row["alert_type"],
                "severity": row["severity"],
                "lat": row["lat"],
                "lon": row["lon"],
                "description": row["description"],
                "acknowledged": row["acknowledged"],
                "acknowledged_by": row["acknowledged_by"],
                "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
            }
        )
    return {"alerts": alerts}


@router.patch("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    body: AlertAcknowledge,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await session.execute(
        text(
            """
            UPDATE alerts
            SET acknowledged = true, acknowledged_by = :by
            WHERE id = :id
            RETURNING id, acknowledged, acknowledged_by
            """
        ),
        {"id": alert_id, "by": body.acknowledged_by},
    )
    await session.commit()
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    return dict(row)
