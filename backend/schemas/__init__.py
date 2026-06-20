"""Pydantic schemas for Helios API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from helios_common.models import AlertSeverity, AoiPriority


class TokenRequest(BaseModel):
    analyst_id: str = Field(..., min_length=1, max_length=255)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GeoJsonGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]


class AoiCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    priority: AoiPriority = AoiPriority.MEDIUM
    geometry: GeoJsonGeometry


class AlertAcknowledge(BaseModel):
    acknowledged_by: str = Field(..., min_length=1, max_length=255)


class DetectionFilters(BaseModel):
    bbox: str | None = None
    time_start: datetime | None = None
    time_end: datetime | None = None
    classes: list[str] | None = None
    confidence_min: float | None = None
    aoi_id: int | None = None


class ChangeFilters(BaseModel):
    aoi_id: int | None = None
    time_start: datetime | None = None
    time_end: datetime | None = None


class AlertFilters(BaseModel):
    aoi_id: int | None = None
    severity: AlertSeverity | None = None
    acknowledged: bool | None = None


class SceneFilters(BaseModel):
    aoi_id: int | None = None


class ExportParams(BaseModel):
    format: Literal["pdf", "csv", "kml", "geojson"]
    bbox: str | None = None
    time_start: datetime | None = None
    time_end: datetime | None = None
    classes: list[str] | None = None
    aoi_id: int | None = None


class GeoJsonFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict[str, Any]]
