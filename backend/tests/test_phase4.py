"""Phase 4 API tests."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from helios_common.auth import create_access_token, verify_token  # noqa: E402
from helios_common.geojson import feature_collection, parse_bbox  # noqa: E402
from services.export_service import _export_csv, _export_kml  # noqa: E402


def test_jwt_roundtrip():
    token = create_access_token("analyst-demo")
    assert verify_token(token) == "analyst-demo"


def test_parse_bbox():
    bounds = parse_bbox("44.0,33.0,44.5,33.5")
    assert bounds == (44.0, 33.0, 44.5, 33.5)


def test_parse_bbox_invalid():
    with pytest.raises(ValueError):
        parse_bbox("1,2,3")


def test_feature_collection():
    fc = feature_collection([])
    assert fc["type"] == "FeatureCollection"
    assert fc["features"] == []


def test_export_csv():
    rows = [
        {
            "detection_id": 1,
            "class": "vehicle",
            "subclass": None,
            "confidence": 0.9,
            "lat": 33.1,
            "lon": 44.2,
            "heading_degrees": 90.0,
            "timestamp": datetime.now(timezone.utc),
            "satellite_source": "copernicus",
        }
    ]
    content = _export_csv(rows)
    assert b"detection_id" in content
    assert b"vehicle" in content


def test_export_kml():
    rows = [
        {
            "detection_id": 1,
            "class": "ship",
            "confidence": 0.8,
            "lat": 33.1,
            "lon": 44.2,
        }
    ]
    content = _export_kml(rows)
    assert b"<kml" in content
    assert b"Placemark" in content


@pytest.mark.asyncio
async def test_health_endpoint():
    httpx = pytest.importorskip("httpx")
    from httpx import ASGITransport, AsyncClient

    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["phase"] == 5


@pytest.mark.asyncio
async def test_protected_route_requires_auth():
    httpx = pytest.importorskip("httpx")
    from httpx import ASGITransport, AsyncClient

    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/aois")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_token_endpoint():
    httpx = pytest.importorskip("httpx")
    from httpx import ASGITransport, AsyncClient

    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/auth/token", json={"analyst_id": "tester"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
