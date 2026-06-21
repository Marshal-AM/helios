"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import {
  createAoi,
  deactivateAoi,
  getAois,
  updateAoi,
} from "@/lib/api";
import type { AoiFeature } from "@/lib/types";

const AoiDrawMap = dynamic(() => import("@/components/aois/AoiDrawMap").then((m) => m.AoiDrawMap), {
  ssr: false,
  loading: () => <div className="auth-loading">Loading map…</div>,
});

export default function AoiManagerPage() {
  const [aois, setAois] = useState<AoiFeature[]>([]);
  const [name, setName] = useState("");
  const [priority, setPriority] = useState<"high" | "medium" | "low">("medium");
  const [polygon, setPolygon] = useState<number[][][] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const loadAois = useCallback(async () => {
    const data = await getAois();
    setAois(data.features);
  }, []);

  useEffect(() => {
    loadAois().catch(console.error);
  }, [loadAois]);

  const handleSave = async () => {
    if (!name.trim() || !polygon) {
      setError("Draw a polygon and enter a name");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createAoi({
        name: name.trim(),
        priority,
        geometry: { type: "Polygon", coordinates: polygon },
      });
      setName("");
      setPolygon(null);
      await loadAois();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create AOI");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (aoi: AoiFeature) => {
    await updateAoi(aoi.properties.aoi_id, {
      monitoring_active: !aoi.properties.monitoring_active,
    });
    await loadAois();
  };

  const handleDelete = async (id: number) => {
    await deactivateAoi(id);
    setDeleteConfirm(null);
    await loadAois();
  };

  return (
    <div className="aoi-page">
      <div className="aoi-list-panel">
        <h2 style={{ color: "#7fdbca", marginBottom: "1rem", fontSize: "1rem" }}>Areas of Interest</h2>
        {aois.length === 0 && (
          <p style={{ color: "#5c7a8a", fontSize: "0.85rem" }}>No AOIs defined yet</p>
        )}
        {aois.map((aoi) => (
          <div key={aoi.properties.aoi_id} className="aoi-list-item">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h4>{aoi.properties.name}</h4>
              <label className="toggle-switch" title="Monitoring active">
                <input
                  type="checkbox"
                  checked={aoi.properties.monitoring_active}
                  onChange={() => handleToggle(aoi)}
                />
                <span className="toggle-slider" />
              </label>
            </div>
            <div className="meta">
              Priority: {aoi.properties.priority}
              <br />
              Last pass:{" "}
              {aoi.properties.last_pass_at
                ? new Date(aoi.properties.last_pass_at).toLocaleString()
                : "Never"}
              <br />
              Detections (7d): {aoi.properties.active_detection_count ?? 0}
            </div>
            <button
              style={{
                marginTop: "0.5rem",
                fontSize: "0.75rem",
                color: "#e06c75",
                background: "none",
                border: "1px solid #e06c75",
                borderRadius: "4px",
                padding: "0.25rem 0.5rem",
                cursor: "pointer",
              }}
              onClick={() => setDeleteConfirm(aoi.properties.aoi_id)}
            >
              Deactivate
            </button>
          </div>
        ))}
      </div>

      <div className="aoi-map-panel">
        <div className="aoi-form">
          <div>
            <label style={{ fontSize: "0.7rem", color: "#5c7a8a" }}>Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="AOI name"
            />
          </div>
          <div>
            <label style={{ fontSize: "0.7rem", color: "#5c7a8a" }}>Priority</label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as typeof priority)}
            >
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
          <button
            className="toolbar-btn active"
            onClick={handleSave}
            disabled={saving}
            style={{ marginBottom: "0.25rem" }}
          >
            {saving ? "Saving…" : "Save AOI"}
          </button>
          {polygon && (
            <span style={{ fontSize: "0.75rem", color: "#98c379" }}>Polygon drawn</span>
          )}
          {error && (
            <span style={{ fontSize: "0.75rem", color: "#e06c75" }}>{error}</span>
          )}
        </div>
        <div className="aoi-map-container">
          <AoiDrawMap onPolygonDrawn={setPolygon} />
        </div>
      </div>

      {deleteConfirm != null && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Deactivate AOI?</h3>
            <p style={{ fontSize: "0.85rem", margin: "0.75rem 0" }}>
              This stops monitoring but keeps historical detections.
            </p>
            <div className="modal-actions">
              <button onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="primary" onClick={() => handleDelete(deleteConfirm)}>
                Deactivate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
