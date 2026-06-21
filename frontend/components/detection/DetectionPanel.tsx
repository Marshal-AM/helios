"use client";

import { useEffect, useState } from "react";
import { fetchGradCamBlob } from "@/lib/api";
import type { DetectionFeature } from "@/lib/types";

type Props = {
  detection: DetectionFeature | null;
  onClose: () => void;
};

export function DetectionPanel({ detection, onClose }: Props) {
  const [gradcamUrl, setGradcamUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!detection) {
      setGradcamUrl(null);
      return;
    }
    let revoked: string | null = null;
    fetchGradCamBlob(detection.properties.detection_id).then((blob) => {
      if (blob) {
        revoked = URL.createObjectURL(blob);
        setGradcamUrl(revoked);
      } else {
        setGradcamUrl(null);
      }
    });
    return () => {
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [detection]);

  if (!detection) return null;
  const p = detection.properties;

  return (
    <div className="panel detection-panel">
      <button className="panel-close" onClick={onClose} aria-label="Close">
        ×
      </button>
      <h3>Detection #{p.detection_id}</h3>
      <div className="row">
        <span>Class</span>
        <span>{p.class}</span>
      </div>
      {p.subclass && (
        <div className="row">
          <span>Subclass</span>
          <span>{p.subclass}</span>
        </div>
      )}
      <div className="row">
        <span>Confidence</span>
        <span>{(p.confidence * 100).toFixed(1)}%</span>
      </div>
      <div className="row">
        <span>Coordinates</span>
        <span>
          {p.lat.toFixed(6)}, {p.lon.toFixed(6)}
        </span>
      </div>
      {p.heading_degrees != null && (
        <div className="row">
          <span>Heading</span>
          <span>{p.heading_degrees.toFixed(1)}°</span>
        </div>
      )}
      <div className="row">
        <span>Timestamp</span>
        <span>{new Date(p.timestamp).toLocaleString()}</span>
      </div>
      <div className="row">
        <span>Source</span>
        <span>{p.satellite_source || "—"}</span>
      </div>
      {gradcamUrl ? (
        <img src={gradcamUrl} alt="Grad-CAM heatmap" className="gradcam" />
      ) : (
        <p className="meta" style={{ marginTop: "0.75rem", fontSize: "0.75rem", color: "#5c7a8a" }}>
          Grad-CAM not available for this detection
        </p>
      )}
    </div>
  );
}
