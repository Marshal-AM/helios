from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, require_auth
from services.export_service import export_detections

router = APIRouter(prefix="/export", tags=["export"])


@router.get("")
async def export_data(
    format: str = Query(..., alias="format", pattern="^(pdf|csv|kml|geojson)$"),
    bbox: str | None = Query(None),
    time_start: datetime | None = Query(None),
    time_end: datetime | None = Query(None),
    classes: list[str] | None = Query(None),
    aoi_id: int | None = Query(None),
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    try:
        content, media_type, filename = await export_detections(
            session,
            format,
            bbox=bbox,
            time_start=time_start,
            time_end=time_end,
            classes=classes,
            aoi_id=aoi_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
