export type GeoJsonPolygon = {
  type: "Polygon";
  coordinates: number[][][];
};

export type AoiProperties = {
  aoi_id: number;
  name: string;
  priority: "high" | "medium" | "low";
  last_pass_at: string | null;
  monitoring_active: boolean;
  last_satellite_source?: string | null;
  last_cloud_cover_pct?: number | null;
  active_detection_count?: number;
};

export type AoiFeature = {
  type: "Feature";
  id: number;
  geometry: GeoJsonPolygon;
  properties: AoiProperties;
};

export type DetectionProperties = {
  detection_id: number;
  class: string;
  subclass: string | null;
  confidence: number;
  lat: number;
  lon: number;
  heading_degrees: number | null;
  timestamp: string;
  scene_id: number | null;
  aoi_id: number | null;
  satellite_source: string | null;
};

export type DetectionFeature = {
  type: "Feature";
  id: number;
  geometry: { type: "Point" | "Polygon"; coordinates: unknown };
  properties: DetectionProperties;
};

export type FeatureCollection<T> = {
  type: "FeatureCollection";
  features: T[];
};

export type ChangeEndpoint = {
  lat: number;
  lon: number;
  class: string;
} | null;

export type ChangeEvent = {
  id: number;
  aoi_id: number;
  event_type: "appeared" | "disappeared" | "moved";
  distance_moved_m: number | null;
  speed_kmh: number | null;
  bearing_degrees: number | null;
  timestamp: string;
  alert_fired: boolean;
  t1: ChangeEndpoint;
  t2: ChangeEndpoint;
};

export type Alert = {
  id: number;
  aoi_id: number;
  aoi_name?: string;
  change_event_id: number | null;
  alert_type: string;
  severity: "critical" | "high" | "medium";
  lat: number;
  lon: number;
  description: string;
  acknowledged: boolean;
  acknowledged_by: string | null;
  timestamp: string;
};

export type Scene = {
  id: number;
  aoi_id: number;
  satellite_source: string;
  external_scene_id: string;
  sensor_type: string;
  acquisition_timestamp: string;
  cloud_cover_pct: number | null;
  scene_path: string | null;
  processed: boolean;
  created_at: string;
};

export type WsEvent =
  | { type: "detection_created"; payload: { feature: DetectionFeature } }
  | { type: "change_detected"; payload: ChangeEvent }
  | {
      type: "alert_fired";
      payload: {
        id: number;
        aoi_id: number;
        aoi_name?: string;
        alert_type: string;
        severity: "critical" | "high" | "medium";
        lat: number;
        lon: number;
        description: string;
        timestamp: string;
      };
    }
  | { type: "scene_processing"; payload: { aoi_id: number; scene_id: number } }
  | { type: "scene_processing_complete"; payload: { aoi_id: number; scene_id: number } }
  | { type: "ping" };

export type DetectionQuery = {
  bbox?: string;
  time_start?: string;
  time_end?: string;
  classes?: string[];
  confidence_min?: number;
  aoi_id?: number;
};

export type ExportQuery = {
  format: "pdf" | "csv" | "kml" | "geojson";
  bbox?: string;
  time_start?: string;
  time_end?: string;
  classes?: string[];
  aoi_id?: number;
};
