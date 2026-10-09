import React, { useEffect } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer, Marker, Popup, Circle, CircleMarker, LayersControl, useMap } from "react-leaflet";

// Fix default marker icon paths
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const SEVERITY_COLOR_HEX = {
  faible: "#10b981",
  moyenne: "#f59e0b",
  haute: "#f97316",
  critique: "#dc2626",
};

const TYPE_ICON_COLOR = {
  deforestation: "#7c2d12",
  agriculture_illegale: "#c9a66b",
  feu_de_brousse: "#dc2626",
  exploitation_illegale: "#a16207",
  defrichement: "#9a3412",
  orpaillage: "#b45309",
};

function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (!points || points.length === 0) return;
    const bounds = L.latLngBounds(points.map((p) => [p.lat, p.lng]));
    if (bounds.isValid()) map.fitBounds(bounds.pad(0.2));
  }, [points, map]);
  return null;
}

export default function ForestMap({
  center = [6.20, -6.0],
  zoom = 10,
  alerts = [],
  observations = [],
  missions = [],
  riskCells = [],
  forests = [],
  height = "100%",
  fit = false,
}) {
  const points = [
    ...alerts.map((a) => ({ lat: a.lat, lng: a.lng })),
    ...observations.map((o) => ({ lat: o.lat, lng: o.lng })),
    ...missions.map((m) => ({ lat: m.target_lat, lng: m.target_lng })),
    ...forests.map((f) => ({ lat: f.center_lat, lng: f.center_lng })),
  ];

  return (
    <div style={{ height }} className="rounded-lg overflow-hidden border border-border" data-testid="forest-map">
      <MapContainer center={center} zoom={zoom} scrollWheelZoom={true} style={{ height: "100%", width: "100%" }}>
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Carte">
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; OpenStreetMap'
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Satellite (Esri)">
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              attribution="Tiles &copy; Esri"
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Topo">
            <TileLayer
              url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
              attribution="&copy; OpenTopoMap"
            />
          </LayersControl.BaseLayer>
        </LayersControl>

        {fit && <FitBounds points={points} />}

        {/* Forests */}
        {forests.map((f) => (
          <Circle
            key={`forest-${f.id}`}
            center={[f.center_lat, f.center_lng]}
            radius={Math.sqrt(f.area_ha * 10000 / Math.PI)}
            pathOptions={{ color: "#1e5128", fillColor: "#4f7942", fillOpacity: 0.15, weight: 2, dashArray: "6 4" }}
          >
            <Popup>
              <div className="text-sm">
                <div className="font-bold">{f.name}</div>
                <div>{f.area_ha.toLocaleString("fr-FR")} ha</div>
                <div className="text-xs text-zinc-600">{f.region}</div>
              </div>
            </Popup>
          </Circle>
        ))}

        {/* Risk cells */}
        {riskCells.map((c, i) => (
          <CircleMarker
            key={`risk-${i}`}
            center={[c.lat, c.lng]}
            radius={6 + c.risk * 8}
            pathOptions={{
              color: c.risk > 0.7 ? "#dc2626" : c.risk > 0.4 ? "#f59e0b" : "#84cc16",
              fillOpacity: 0.5,
              weight: 1,
            }}
          >
            <Popup>Risque déforestation: {(c.risk * 100).toFixed(0)}%</Popup>
          </CircleMarker>
        ))}

        {/* Alerts */}
        {alerts.map((a) => (
          <CircleMarker
            key={`alert-${a.id}`}
            center={[a.lat, a.lng]}
            radius={8}
            pathOptions={{
              color: SEVERITY_COLOR_HEX[a.severity] || "#dc2626",
              fillColor: SEVERITY_COLOR_HEX[a.severity] || "#dc2626",
              fillOpacity: 0.7,
              weight: 2,
            }}
          >
            <Popup>
              <div className="text-sm">
                <div className="font-bold capitalize">{(a.alert_type || "").replace(/_/g, " ")}</div>
                <div>Sévérité: {a.severity}</div>
                <div>Statut: {a.status}</div>
                <div className="text-xs text-zinc-600">Surface: {a.area_ha} ha</div>
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {/* Observations */}
        {observations.map((o) => (
          <Marker key={`obs-${o.id}`} position={[o.lat, o.lng]}>
            <Popup>
              <div className="text-sm">
                <div className="font-bold">{o.observation_type?.replace(/_/g, " ")}</div>
                <div>{o.description}</div>
                <div className="text-xs text-zinc-600">par {o.agent_name}</div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Missions */}
        {missions.map((m) => (
          <Circle
            key={`mission-${m.id}`}
            center={[m.target_lat, m.target_lng]}
            radius={m.radius_m || 500}
            pathOptions={{ color: "#0ea5e9", fillColor: "#0ea5e9", fillOpacity: 0.15, weight: 1.5 }}
          >
            <Popup>
              <div className="text-sm">
                <div className="font-bold">Mission drone</div>
                <div>{m.purpose}</div>
                <div>Statut: {m.status}</div>
              </div>
            </Popup>
          </Circle>
        ))}
      </MapContainer>
    </div>
  );
}
