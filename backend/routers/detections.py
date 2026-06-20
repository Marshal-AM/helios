from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, require_auth
from services.queries import fetch_detections_geojson

router = APIRouter(prefix="/detections", tags=["detections"])


@router.get("")
async def list_detections(
    bbox: str | None = Query(None),
    time_start: datetime | None = Query(None),
    time_end: datetime | None = Query(None),
    classes: list[str] | None = Query(None),
    confidence_min: float | None = Query(None),
    aoi_id: int | None = Query(None),
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    return await fetch_detections_geojson(
        session,
        bbox=bbox,
        time_start=time_start,
        time_end=time_end,
        classes=classes,
        confidence_min=confidence_min,
        aoi_id=aoi_id,
    )


@router.get("/{detection_id}/gradcam")
async def get_detection_gradcam(
    detection_id: int,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await session.execute(
        text("SELECT gradcam_path FROM detections WHERE id = :id"),
        {"id": detection_id},
    )
    row = result.first()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="Grad-CAM not found for detection")

    path = Path(row[0])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Grad-CAM file missing on disk")

    return FileResponse(path, media_type="image/png", filename=f"gradcam_{detection_id}.png")
