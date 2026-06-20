#!/usr/bin/env python3
"""Seed demo data for Phase 4 API testing."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import text  # noqa: E402

from helios_common.db import SyncSessionLocal  # noqa: E402


def main() -> None:
    wkt = "POLYGON((44.0 33.0, 44.5 33.0, 44.5 33.5, 44.0 33.5, 44.0 33.0))"
    now = datetime.now(timezone.utc)

    with SyncSessionLocal() as session:
        aoi_id = session.execute(
            text(
                """
                INSERT INTO aois (name, priority, polygon, monitoring_active, last_pass_at)
                VALUES ('Demo AOI', 'high', ST_GeomFromText(:wkt, 4326), true, :now)
                RETURNING id
                """
            ),
            {"wkt": wkt, "now": now},
        ).scalar()

        if not aoi_id:
            aoi_id = session.execute(text("SELECT id FROM aois WHERE name = 'Demo AOI'")).scalar()

        scene_id = session.execute(
            text(
                """
                INSERT INTO scenes (aoi_id, satellite_source, external_scene_id, sensor_type,
                                    acquisition_timestamp, cloud_cover_pct, processed)
                VALUES (:aoi, 'copernicus', 'demo-scene-001', 'sentinel-2', :now, 0.1, true)
                ON CONFLICT (external_scene_id) DO UPDATE SET processed = true
                RETURNING id
                """
            ),
            {"aoi": aoi_id, "now": now},
        ).scalar()

        session.execute(
            text(
                """
                INSERT INTO detections (scene_id, aoi_id, class, confidence, lat, lon,
                                        bbox_polygon, timestamp)
                SELECT :scene, :aoi, 'vehicle', 0.92, 33.25, 44.25,
                       ST_GeomFromText('POINT(44.25 33.25)', 4326), :now
                WHERE NOT EXISTS (
                    SELECT 1 FROM detections WHERE scene_id = :scene AND class = 'vehicle'
                )
                """
            ),
            {"scene": scene_id, "aoi": aoi_id, "now": now},
        )
        session.commit()
        print(f"Seeded AOI={aoi_id} scene={scene_id}")


if __name__ == "__main__":
    main()
