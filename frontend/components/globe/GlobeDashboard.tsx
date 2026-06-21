"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { loadCesium, type CesiumNamespace } from "@/lib/cesium-loader";
import { getAois, getChanges, getDetections, getScenes } from "@/lib/api";
import { HeliosWebSocket } from "@/lib/ws";
import { iconForClass, scaleForConfidence, CHANGE_COLORS } from "@/lib/icons";
import type {
  Alert,
  AoiFeature,
  ChangeEvent,
  DetectionFeature,
  Scene,
  WsEvent,
} from "@/lib/types";
import { DetectionPanel } from "@/components/detection/DetectionPanel";
import { AlertPanel } from "@/components/alerts/AlertPanel";
import { TimelineScrubber } from "@/components/timeline/TimelineScrubber";
import { ExportModal } from "@/components/export/ExportModal";

const ION_TOKEN = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN || "";

function aoiBbox(coords: number[][][]) {
  const ring = coords[0];
  let west = Infinity,
    east = -Infinity,
    south = Infinity,
    north = -Infinity;
  ring.forEach(([lon, lat]) => {
    west = Math.min(west, lon);
    east = Math.max(east, lon);
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  });
  return { west, south, east, north };
}

function aoiCentroid(coords: number[][][]) {
  const ring = coords[0];
  const n = ring.length - 1;
  let lon = 0,
    lat = 0;
  for (let i = 0; i < n; i++) {
    lon += ring[i][0];
    lat += ring[i][1];
  }
  return { lon: lon / n, lat: lat / n };
}

function coverageColor(Cesium: CesiumNamespace, hoursAgo: number) {
  if (hoursAgo < 6) return Cesium.Color.fromCssColorString("#98c379").withAlpha(0.35);
  if (hoursAgo < 48) return Cesium.Color.fromCssColorString("#e5c07b").withAlpha(0.35);
  return Cesium.Color.fromCssColorString("#e06c75").withAlpha(0.35);
}

export default function GlobeDashboard() {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const cesiumRef = useRef<CesiumNamespace | null>(null);
  const entityMapRef = useRef<Map<string, DetectionFeature | ChangeEvent>>(new Map());
  const handlerRef = useRef<any>(null);

  const [cesiumReady, setCesiumReady] = useState(false);
  const [aois, setAois] = useState<AoiFeature[]>([]);
  const [detections, setDetections] = useState<DetectionFeature[]>([]);
  const [allDetections, setAllDetections] = useState<DetectionFeature[]>([]);
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [scenesByAoi, setScenesByAoi] = useState<Map<number, Scene>>(new Map());
  const [selectedDetection, setSelectedDetection] = useState<DetectionFeature | null>(null);
  const [selectedChange, setSelectedChange] = useState<ChangeEvent | null>(null);
  const [processingAois, setProcessingAois] = useState<Set<number>>(new Set());
  const [pulseOn, setPulseOn] = useState(true);
  const [isLive, setIsLive] = useState(true);
  const [timeEnd, setTimeEnd] = useState<Date | null>(null);
  const [showDetections, setShowDetections] = useState(true);
  const [showAois, setShowAois] = useState(true);
  const [showChanges, setShowChanges] = useState(true);
  const [showCoverage, setShowCoverage] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [newAlerts, setNewAlerts] = useState<Alert[]>([]);
  const [flyTarget, setFlyTarget] = useState<{ lon: number; lat: number } | null>(null);
  const initialFlyDone = useRef(false);

  const pulseAlpha = pulseOn ? 0.9 : 0.3;

  useEffect(() => {
    const id = setInterval(() => setPulseOn((p) => !p), 500);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    let destroyed = false;
    loadCesium()
      .then((Cesium) => {
        if (destroyed || !containerRef.current) return;
        cesiumRef.current = Cesium;
        const viewer = new Cesium.Viewer(containerRef.current, {
          timeline: false,
          animation: false,
          baseLayerPicker: false,
          geocoder: false,
          homeButton: true,
          navigationHelpButton: false,
          sceneModePicker: false,
          terrain: Cesium.Terrain.fromWorldTerrain(),
        });
        viewerRef.current = viewer;

        const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
        handler.setInputAction((movement: { position: { x: number; y: number } }) => {
          const picked = viewer.scene.pick(movement.position);
          if (!Cesium.defined(picked) || !picked.id) return;
          const id = picked.id.id as string;
          const data = entityMapRef.current.get(id);
          if (!data) return;
          if ("properties" in data) {
            setSelectedDetection(data as DetectionFeature);
            setSelectedChange(null);
          } else {
            setSelectedChange(data as ChangeEvent);
            setSelectedDetection(null);
          }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
        handlerRef.current = handler;

        setCesiumReady(true);
      })
      .catch(console.error);

    return () => {
      destroyed = true;
      handlerRef.current?.destroy();
      viewerRef.current?.destroy();
      viewerRef.current = null;
    };
  }, []);

  const loadData = useCallback(async () => {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const [aoiData, changeData, detAll] = await Promise.all([
      getAois(),
      getChanges(),
      getDetections({ time_start: thirtyDaysAgo.toISOString() }),
    ]);

    setAois(aoiData.features);
    setChanges(changeData.events);
    setAllDetections(detAll.features);
    setDetections(detAll.features);

    if (aoiData.features.length > 0 && !initialFlyDone.current) {
      const c = aoiCentroid(aoiData.features[0].geometry.coordinates);
      setFlyTarget(c);
      initialFlyDone.current = true;
    }

    const sceneMap = new Map<number, Scene>();
    await Promise.all(
      aoiData.features.map(async (a) => {
        const { scenes } = await getScenes(a.properties.aoi_id);
        if (scenes[0]) sceneMap.set(a.properties.aoi_id, scenes[0]);
      })
    );
    setScenesByAoi(sceneMap);
  }, []);

  useEffect(() => {
    loadData().catch(console.error);
  }, [loadData]);

  const refreshDetections = useCallback(async (end?: Date | null) => {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    const params: { time_start: string; time_end?: string } = {
      time_start: thirtyDaysAgo.toISOString(),
    };
    if (end) params.time_end = end.toISOString();
    const data = await getDetections(params);
    setDetections(data.features);
    if (!end) setAllDetections(data.features);
  }, []);

  useEffect(() => {
    if (!isLive && timeEnd) refreshDetections(timeEnd).catch(console.error);
  }, [isLive, timeEnd, refreshDetections]);

  useEffect(() => {
    const ws = new HeliosWebSocket({
      onEvent: (event: WsEvent) => {
        if (event.type === "detection_created" && isLive) {
          const f = event.payload.feature;
          setDetections((prev) => {
            if (prev.some((d) => d.properties.detection_id === f.properties.detection_id)) return prev;
            return [f, ...prev];
          });
          setAllDetections((prev) => {
            if (prev.some((d) => d.properties.detection_id === f.properties.detection_id)) return prev;
            return [f, ...prev];
          });
        } else if (event.type === "change_detected") {
          setChanges((prev) => {
            if (prev.some((c) => c.id === event.payload.id)) return prev;
            return [event.payload, ...prev];
          });
        } else if (event.type === "alert_fired") {
          const p = event.payload;
          setNewAlerts((prev) => [
            {
              id: p.id,
              aoi_id: p.aoi_id,
              aoi_name: p.aoi_name,
              change_event_id: null,
              alert_type: p.alert_type,
              severity: p.severity,
              lat: p.lat,
              lon: p.lon,
              description: p.description,
              acknowledged: false,
              acknowledged_by: null,
              timestamp: p.timestamp,
            },
            ...prev,
          ]);
        } else if (event.type === "scene_processing") {
          setProcessingAois((prev) => new Set(prev).add(event.payload.aoi_id));
        } else if (event.type === "scene_processing_complete") {
          setProcessingAois((prev) => {
            const next = new Set(prev);
            next.delete(event.payload.aoi_id);
            return next;
          });
          getScenes(event.payload.aoi_id).then(({ scenes }) => {
            if (scenes[0]) setScenesByAoi((m) => new Map(m).set(event.payload.aoi_id, scenes[0]));
          });
          getAois().then((d) => setAois(d.features));
        }
      },
      onReconnect: () => {
        if (isLive) refreshDetections().catch(console.error);
      },
    });
    ws.connect().catch(console.error);
    return () => ws.disconnect();
  }, [isLive, refreshDetections]);

  useEffect(() => {
    const viewer = viewerRef.current;
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium || !cesiumReady) return;

    viewer.entities.removeAll();
    entityMapRef.current.clear();

    if (showAois) {
      aois.forEach((aoi) => {
        const props = aoi.properties;
        const isProcessing = processingAois.has(props.aoi_id);
        const outlineAlpha = isProcessing ? pulseAlpha : 0.85;
        const scene = scenesByAoi.get(props.aoi_id);
        const tooltip = [
          props.name,
          `Priority: ${props.priority}`,
          props.last_pass_at
            ? `Last pass: ${new Date(props.last_pass_at).toLocaleString()}`
            : "No passes yet",
          props.last_satellite_source
            ? `Satellite: ${props.last_satellite_source}`
            : scene
              ? `Satellite: ${scene.satellite_source}`
              : "",
          `Active detections: ${props.active_detection_count ?? 0}`,
        ]
          .filter(Boolean)
          .join("\n");

        const positions = aoi.geometry.coordinates[0].map(([lon, lat]) =>
          Cesium.Cartesian3.fromDegrees(lon, lat)
        );

        viewer.entities.add({
          name: tooltip,
          polygon: {
            hierarchy: positions,
            material: Cesium.Color.fromCssColorString("#61afef").withAlpha(0.12),
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString("#61afef").withAlpha(outlineAlpha),
            outlineWidth: isProcessing ? 4 : 2,
          },
        });
      });
    }

    if (showCoverage) {
      aois.forEach((aoi) => {
        const scene = scenesByAoi.get(aoi.properties.aoi_id);
        if (!scene) return;
        const hoursAgo =
          (Date.now() - new Date(scene.acquisition_timestamp).getTime()) / 3600000;
        const bbox = aoiBbox(aoi.geometry.coordinates);
        const tooltip = [
          `Last pass: ${new Date(scene.acquisition_timestamp).toLocaleString()}`,
          `Satellite: ${scene.satellite_source}`,
          scene.cloud_cover_pct != null
            ? `Cloud cover: ${(scene.cloud_cover_pct * 100).toFixed(0)}%`
            : "",
        ]
          .filter(Boolean)
          .join("\n");

        viewer.entities.add({
          name: tooltip,
          rectangle: {
            coordinates: Cesium.Rectangle.fromDegrees(
              bbox.west,
              bbox.south,
              bbox.east,
              bbox.north
            ),
            material: coverageColor(Cesium, hoursAgo),
          },
        });
      });
    }

    if (showChanges) {
      changes.forEach((ch) => {
        if (!ch.t1 || !ch.t2) return;
        const color = CHANGE_COLORS[ch.event_type] || "#e5c07b";
        const width = Math.min(Math.max((ch.speed_kmh || 10) / 20, 2), 8);
        const id = `ch-${ch.id}`;
        entityMapRef.current.set(id, ch);
        viewer.entities.add({
          id,
          name: `${ch.event_type} — ${ch.t2.class}`,
          polyline: {
            positions: Cesium.Cartesian3.fromDegreesArray([
              ch.t1.lon,
              ch.t1.lat,
              ch.t2.lon,
              ch.t2.lat,
            ]),
            width,
            material: new Cesium.PolylineArrowMaterialProperty(
              Cesium.Color.fromCssColorString(color)
            ),
          },
        });
      });
    }

    if (showDetections) {
      detections.forEach((det) => {
        const p = det.properties;
        const id = `det-${p.detection_id}`;
        entityMapRef.current.set(id, det);
        viewer.entities.add({
          id,
          position: Cesium.Cartesian3.fromDegrees(p.lon, p.lat, 0),
          name: `${p.class} (${(p.confidence * 100).toFixed(0)}%)`,
          billboard: {
            image: iconForClass(p.class),
            scale: scaleForConfidence(p.confidence),
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          },
        });
      });
    }
  }, [
    cesiumReady,
    aois,
    detections,
    changes,
    scenesByAoi,
    processingAois,
    pulseAlpha,
    showAois,
    showDetections,
    showChanges,
    showCoverage,
  ]);

  useEffect(() => {
    const viewer = viewerRef.current;
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium || !flyTarget) return;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(flyTarget.lon, flyTarget.lat, 250000),
      duration: 1.5,
    });
  }, [flyTarget, cesiumReady]);

  const handleGoLive = () => {
    setIsLive(true);
    setTimeEnd(null);
    refreshDetections().catch(console.error);
  };

  const handleFlyTo = (lat: number, lon: number) => {
    setFlyTarget({ lat, lon });
    setSelectedDetection(null);
    setSelectedChange(null);
  };

  if (!ION_TOKEN) {
    return (
      <div className="auth-error">
        <h2>Cesium Ion token required</h2>
        <p>
          Set <code>CESIUM_ION_TOKEN</code> or <code>NEXT_PUBLIC_CESIUM_ION_TOKEN</code> in{" "}
          <code>frontend/.env</code> and rebuild.
        </p>
      </div>
    );
  }

  return (
    <div className="globe-container">
      <div className="globe-toolbar">
        <button
          className={`toolbar-btn ${showDetections ? "active" : ""}`}
          onClick={() => setShowDetections((v) => !v)}
        >
          Detections
        </button>
        <button
          className={`toolbar-btn ${showAois ? "active" : ""}`}
          onClick={() => setShowAois((v) => !v)}
        >
          AOIs
        </button>
        <button
          className={`toolbar-btn ${showChanges ? "active" : ""}`}
          onClick={() => setShowChanges((v) => !v)}
        >
          Vectors
        </button>
        <button
          className={`toolbar-btn ${showCoverage ? "active" : ""}`}
          onClick={() => setShowCoverage((v) => !v)}
        >
          Coverage
        </button>
        <button className="toolbar-btn" onClick={() => setExportOpen(true)}>
          Export
        </button>
      </div>

      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />

      {!cesiumReady && (
        <div className="auth-loading" style={{ position: "absolute", inset: 0 }}>
          Loading 3D globe…
        </div>
      )}

      <DetectionPanel detection={selectedDetection} onClose={() => setSelectedDetection(null)} />

      {selectedChange && (
        <div className="panel change-detail-panel">
          <button className="panel-close" onClick={() => setSelectedChange(null)}>
            ×
          </button>
          <h3>Change Event #{selectedChange.id}</h3>
          <div className="row">
            <span>Type</span>
            <span>{selectedChange.event_type}</span>
          </div>
          <div className="row">
            <span>Class</span>
            <span>{selectedChange.t2?.class || selectedChange.t1?.class || "—"}</span>
          </div>
          {selectedChange.distance_moved_m != null && (
            <div className="row">
              <span>Distance</span>
              <span>{selectedChange.distance_moved_m.toFixed(0)} m</span>
            </div>
          )}
          {selectedChange.speed_kmh != null && (
            <div className="row">
              <span>Speed</span>
              <span>{selectedChange.speed_kmh.toFixed(1)} km/h</span>
            </div>
          )}
          {selectedChange.bearing_degrees != null && (
            <div className="row">
              <span>Bearing</span>
              <span>{selectedChange.bearing_degrees.toFixed(1)}°</span>
            </div>
          )}
          <div className="row">
            <span>Time</span>
            <span>{new Date(selectedChange.timestamp).toLocaleString()}</span>
          </div>
        </div>
      )}

      <AlertPanel aois={aois} onFlyTo={handleFlyTo} externalAlerts={newAlerts} />

      <TimelineScrubber
        detections={allDetections}
        isLive={isLive}
        timeEnd={timeEnd}
        onTimeEndChange={(d) => {
          setIsLive(false);
          setTimeEnd(d);
        }}
        onGoLive={handleGoLive}
      />

      <ExportModal open={exportOpen} onClose={() => setExportOpen(false)} aois={aois} />
    </div>
  );
}
