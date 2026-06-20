"""Export detections to PDF, CSV, KML, GeoJSON."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.ext.asyncio import AsyncSession

from services.queries import fetch_detection_rows, fetch_detections_geojson


async def export_detections(
    session: AsyncSession,
    fmt: str,
    *,
    bbox: str | None = None,
    time_start: datetime | None = None,
    time_end: datetime | None = None,
    classes: list[str] | None = None,
    aoi_id: int | None = None,
) -> tuple[bytes, str, str]:
    if fmt == "geojson":
        data = await fetch_detections_geojson(
            session,
            bbox=bbox,
            time_start=time_start,
            time_end=time_end,
            classes=classes,
            aoi_id=aoi_id,
        )
        import json

        content = json.dumps(data, indent=2).encode("utf-8")
        return content, "application/geo+json", "detections.geojson"

    rows = await fetch_detection_rows(
        session,
        bbox=bbox,
        time_start=time_start,
        time_end=time_end,
        classes=classes,
        aoi_id=aoi_id,
    )

    if fmt == "csv":
        return _export_csv(rows), "text/csv", "detections.csv"
    if fmt == "kml":
        return _export_kml(rows), "application/vnd.google-earth.kml+xml", "detections.kml"
    if fmt == "pdf":
        return _export_pdf(rows), "application/pdf", "mission_report.pdf"
    raise ValueError(f"Unsupported format: {fmt}")


def _export_csv(rows: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "detection_id",
            "class",
            "subclass",
            "confidence",
            "lat",
            "lon",
            "heading_degrees",
            "timestamp",
            "satellite_source",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "detection_id": row["detection_id"],
                "class": row["class"],
                "subclass": row.get("subclass") or "",
                "confidence": row["confidence"],
                "lat": row["lat"],
                "lon": row["lon"],
                "heading_degrees": row.get("heading_degrees") or "",
                "timestamp": row["timestamp"].isoformat() if row["timestamp"] else "",
                "satellite_source": row.get("satellite_source") or "",
            }
        )
    return buf.getvalue().encode("utf-8")


def _class_style(class_name: str) -> str:
    mapping = {
        "aircraft": "http://maps.google.com/mapfiles/kml/paddle/ylw-stars.png",
        "plane": "http://maps.google.com/mapfiles/kml/paddle/ylw-stars.png",
        "ship": "http://maps.google.com/mapfiles/kml/paddle/blu-circle.png",
        "vehicle": "http://maps.google.com/mapfiles/kml/paddle/red-circle.png",
        "helicopter": "http://maps.google.com/mapfiles/kml/paddle/orange-circle.png",
    }
    return mapping.get(class_name.lower(), "http://maps.google.com/mapfiles/kml/paddle/wht-blank.png")


def _export_kml(rows: list[dict[str, Any]]) -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "<Document>",
        "<name>Helios Detections</name>",
    ]
    for row in rows:
        cls = row["class"]
        lines.extend(
            [
                "<Placemark>",
                f"<name>{cls} ({row['confidence']:.2f})</name>",
                "<Style>",
                "<IconStyle>",
                f"<Icon><href>{_class_style(cls)}</href></Icon>",
                "</IconStyle>",
                "</Style>",
                "<Point>",
                f"<coordinates>{row['lon']},{row['lat']},0</coordinates>",
                "</Point>",
                "</Placemark>",
            ]
        )
    lines.extend(["</Document>", "</kml>"])
    return "\n".join(lines).encode("utf-8")


def _export_pdf(rows: list[dict[str, Any]]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Helios Mission Report", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Total detections: {len(rows)}", styles["Normal"]),
        Spacer(1, 12),
    ]

    by_class: dict[str, int] = {}
    for row in rows:
        by_class[row["class"]] = by_class.get(row["class"], 0) + 1
    if by_class:
        counts = Paragraph(
            "Counts by class: " + ", ".join(f"{k}={v}" for k, v in sorted(by_class.items())),
            styles["Normal"],
        )
        story.extend([counts, Spacer(1, 12)])

    table_data = [
        ["ID", "Class", "Conf", "Lat", "Lon", "Time", "Source"],
    ]
    for row in rows[:500]:
        table_data.append(
            [
                str(row["detection_id"]),
                row["class"],
                f"{row['confidence']:.2f}",
                f"{row['lat']:.5f}",
                f"{row['lon']:.5f}",
                row["timestamp"].strftime("%Y-%m-%d %H:%M") if row["timestamp"] else "",
                row.get("satellite_source") or "",
            ]
        )
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buf.getvalue()
