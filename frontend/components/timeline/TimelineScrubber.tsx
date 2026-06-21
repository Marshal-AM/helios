"use client";

import type { DetectionFeature } from "@/lib/types";
import { useMemo } from "react";

type Props = {
  detections: DetectionFeature[];
  isLive: boolean;
  timeEnd: Date | null;
  onTimeEndChange: (d: Date | null) => void;
  onGoLive: () => void;
};

export function TimelineScrubber({
  detections,
  isLive,
  timeEnd,
  onTimeEndChange,
  onGoLive,
}: Props) {
  const now = useMemo(() => new Date(), []);
  const start = useMemo(() => {
    const d = new Date(now);
    d.setDate(d.getDate() - 30);
    return d;
  }, [now]);

  const dailyCounts = useMemo(() => {
    const buckets = new Array(30).fill(0);
    const msPerDay = 86400000;
    detections.forEach((f) => {
      const t = new Date(f.properties.timestamp).getTime();
      const dayIdx = Math.floor((t - start.getTime()) / msPerDay);
      if (dayIdx >= 0 && dayIdx < 30) buckets[dayIdx]++;
    });
    const max = Math.max(...buckets, 1);
    return buckets.map((c) => c / max);
  }, [detections, start]);

  const sliderValue = timeEnd
    ? Math.round((timeEnd.getTime() - start.getTime()) / 86400000)
    : 30;

  return (
    <div className="timeline-bar">
      <div className="timeline-chart">
        {dailyCounts.map((h, i) => (
          <div
            key={i}
            className="timeline-bar-col"
            style={{ height: `${Math.max(h * 100, 4)}%` }}
            title={`Day ${i + 1}`}
          />
        ))}
      </div>
      <div className="timeline-controls">
        <span style={{ fontSize: "0.7rem", color: "#5c7a8a", minWidth: "80px" }}>
          {start.toLocaleDateString()}
        </span>
        <input
          type="range"
          min={0}
          max={30}
          value={sliderValue}
          disabled={isLive}
          onChange={(e) => {
            const day = Number(e.target.value);
            const d = new Date(start);
            d.setDate(d.getDate() + day);
            onTimeEndChange(d);
          }}
        />
        <span style={{ fontSize: "0.7rem", color: "#5c7a8a", minWidth: "100px" }}>
          {timeEnd ? timeEnd.toLocaleString() : "Live"}
        </span>
        <button
          className={`timeline-live-btn ${isLive ? "" : "inactive"}`}
          onClick={onGoLive}
        >
          LIVE
        </button>
      </div>
    </div>
  );
}
