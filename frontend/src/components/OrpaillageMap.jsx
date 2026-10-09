import React, { useEffect } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Popup, LayersControl, useMap } from "react-leaflet";
import { DETECTION_LEVEL_HEX, DETECTION_STATUS_LABEL, DETECTION_LEVEL_LABEL } from "@/lib/constants";

function FitZone({ zone }) {
  const map = useMap();
  useEffect(() => {
    if (!zone) return;
    const b = zone.bbox;
    map.fitBounds([[b.min_lat, b.min_lng], [b.max_lat, b.max_lng]], { padding: [20, 20] });
  }, [zone, map]);
  return null;
}

function FlyTo({ target }) {
  const map = useMap();
  useEffect(() => {
    if (!target) return;
    const layer = L.geoJSON(target.geometry);
    map.flyToBounds(layer.getBounds().pad(2), { maxZoom: 16, duration: 0.8 });
  }, [target, map]);
  return null;
}

function styleFor(d, selectedId) {
  const color = d.status === "infirme" ? "#71717a" : DETECTION_LEVEL_HEX[d.level] || "#dc2626";
  return {
    color,
    weight: d.id === selectedId ? 4 : 2,
    fillColor: color,
    fillOpacity: d.status === "confirme" ? 0.55 : d.status === "infirme" ? 0.1 : 0.3,
    dashArray: d.status === "presume" ? "4 3" : null,
  };
}

export default function OrpaillageMap({ zone, detections = [], sites = [], selected, onSelect }) {
  return (
    <div className="h-full rounded-lg overflow-hidden border border-border" data-testid="orpaillage-map">
      <MapContainer center={[6.15, -5.75]} zoom={9} scrollWheelZoom style={{ height: "100%", width: "100%" }}>
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Satellite (Esri)">
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              attribution="Tiles &copy; Esri"
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Carte">
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Topo">
            <TileLayer url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png" attribution="&copy; OpenTopoMap" />
          </LayersControl.BaseLayer>
        </LayersControl>

        <FitZone zone={zone} />
        <FlyTo target={selected} />

        {zone && (
          <GeoJSON
            key={`zone-${zone.id}`}
            data={zone.geometry}
            style={{ color: "#facc15", weight: 2, fill: false, dashArray: "8 6" }}
            interactive={false}
          />
        )}

        {detections.map((d) => (
          <GeoJSON
            key={`${d.id}-${d.status}-${selected?.id === d.id}`}
            data={d.geometry}
            style={() => styleFor(d, selected?.id)}
            eventHandlers={{ click: () => onSelect && onSelect(d) }}
          >
            <Popup>
              <div className="text-sm space-y-0.5">
                <div className="font-bold font-mono">{d.code}</div>
                <div>Score {(d.score * 100).toFixed(0)} % · suspicion {DETECTION_LEVEL_LABEL[d.level]}</div>
                <div>{d.area_ha} ha · {DETECTION_STATUS_LABEL[d.status]}</div>
                <div className="text-xs text-zinc-600 font-mono">{d.lat.toFixed(5)}, {d.lng.toFixed(5)}</div>
              </div>
            </Popup>
          </GeoJSON>
        ))}

        {sites.map((s) => (
          <CircleMarker
            key={`site-${s.id}`}
            center={[s.lat, s.lng]}
            radius={5}
            pathOptions={{ color: "#0f172a", weight: 2, fillColor: "#38bdf8", fillOpacity: 0.9 }}
          >
            <Popup>
              <div className="text-sm">
                <div className="font-bold">{s.name}</div>
                <div>Site connu · {s.status}</div>
                {s.locality && <div className="text-xs text-zinc-600">{s.locality}</div>}
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
