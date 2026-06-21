"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";
import "leaflet-draw";

type Props = {
  onPolygonDrawn: (coords: number[][][]) => void;
  center?: [number, number];
};

export function AoiDrawMap({ onPolygonDrawn, center = [33.25, 44.25] }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const drawnItemsRef = useRef<L.FeatureGroup | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current).setView(center, 8);
    mapRef.current = map;

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    drawnItemsRef.current = drawnItems;

    const drawControl = new L.Control.Draw({
      draw: {
        marker: false,
        circle: false,
        circlemarker: false,
        polyline: false,
        rectangle: false,
        polygon: {
          allowIntersection: false,
          showArea: true,
        },
      },
      edit: {
        featureGroup: drawnItems,
      },
    });
    map.addControl(drawControl);

    map.on(L.Draw.Event.CREATED, (e: L.LeafletEvent) => {
      const event = e as L.DrawEvents.Created;
      const layer = event.layer;
      drawnItems.clearLayers();
      drawnItems.addLayer(layer);
      const geo = layer.toGeoJSON();
      if (geo.geometry.type === "Polygon") {
        onPolygonDrawn(geo.geometry.coordinates as number[][][]);
      }
    });

    map.on(L.Draw.Event.EDITED, () => {
      drawnItems.eachLayer((layer) => {
        const geo = (layer as L.Polygon).toGeoJSON();
        if (geo.geometry.type === "Polygon") {
          onPolygonDrawn(geo.geometry.coordinates as number[][][]);
        }
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [center, onPolygonDrawn]);

  return <div ref={containerRef} style={{ width: "100%", height: "100%" }} />;
}
