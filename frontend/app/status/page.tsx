"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";

export default function StatusPage() {
  const [health, setHealth] = useState<{
    status: string;
    db?: string;
    phase?: number;
    ws_clients?: number;
    error?: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getHealth()
      .then((data) => {
        setHealth(data);
        setLoading(false);
      })
      .catch(() => {
        setHealth({ status: "error", error: "Cannot reach API" });
        setLoading(false);
      });
  }, []);

  const statusClass =
    health?.status === "ok"
      ? "status-ok"
      : health?.status === "error"
        ? "status-error"
        : "status-pending";

  return (
    <main className="status-page">
      <h1>Helios System Status</h1>
      <p className="subtitle" style={{ color: "#5c7a8a", marginBottom: "1.5rem" }}>
        Infrastructure health check
      </p>
      <div className="card">
        <h2 style={{ fontSize: "0.85rem", color: "#5c7a8a", marginBottom: "0.75rem" }}>API Health</h2>
        {loading ? (
          <p className="status-pending">Checking…</p>
        ) : (
          <>
            <p className={statusClass}>
              Status: {health?.status ?? "unknown"}
              {health?.db ? ` | DB: ${health.db}` : ""}
              {health?.phase != null ? ` | Phase: ${health.phase}` : ""}
              {health?.ws_clients != null ? ` | WS clients: ${health.ws_clients}` : ""}
            </p>
            {health?.error && <p style={{ fontFamily: "monospace", fontSize: "0.9rem" }}>{health.error}</p>}
          </>
        )}
      </div>
    </main>
  );
}
