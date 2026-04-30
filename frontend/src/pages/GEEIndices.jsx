import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Satellite, TrendingDown, TrendingUp } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, PieChart, Pie, Cell } from "recharts";

export default function GEEIndices() {
  const [forests, setForests] = useState([]);
  const [forestId, setForestId] = useState("");
  const [indices, setIndices] = useState(null);
  const [landcover, setLandcover] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const f = await api.get("/forests");
      setForests(f.data);
      if (f.data.length) setForestId(f.data[0].id);
    })();
  }, []);

  useEffect(() => {
    if (!forestId) return;
    setLoading(true);
    Promise.all([
      api.get(`/gee/indices/${forestId}`),
      api.get(`/gee/landcover/${forestId}`),
    ])
      .then(([a, b]) => { setIndices(a.data); setLandcover(b.data); })
      .finally(() => setLoading(false));
  }, [forestId]);

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="gee-page">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Google Earth Engine</div>
          <h1 className="font-display font-bold text-3xl lg:text-4xl tracking-tight mt-1">Indices spectraux & couverture</h1>
          <p className="text-sm text-muted-foreground mt-1">NDVI · NBR · NDWI · Classification de couverture des sols</p>
        </div>
        <Select value={forestId} onValueChange={setForestId}>
          <SelectTrigger className="w-72" data-testid="gee-forest-select"><SelectValue /></SelectTrigger>
          <SelectContent>{forests.map((f) => <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>)}</SelectContent>
        </Select>
      </header>

      {loading || !indices ? (
        <Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="p-5 border border-border shadow-none">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold">NDVI actuel</div>
              <div className="mt-2 font-display text-3xl font-light text-primary">{indices.summary.ndvi_current}</div>
              <div className="mt-1 text-xs text-muted-foreground">indice de végétation</div>
            </Card>
            <Card className="p-5 border border-border shadow-none">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold">Tendance NDVI</div>
              <div className={`mt-2 font-display text-3xl font-light flex items-center gap-2 ${indices.summary.ndvi_trend < 0 ? "text-destructive" : "text-emerald-700"}`}>
                {indices.summary.ndvi_trend < 0 ? <TrendingDown className="w-6 h-6" /> : <TrendingUp className="w-6 h-6" />}
                {indices.summary.ndvi_trend > 0 ? "+" : ""}{indices.summary.ndvi_trend}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">12 derniers mois</div>
            </Card>
            <Card className="p-5 border border-border shadow-none">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold">Statut</div>
              <div className="mt-2 font-display text-3xl font-light capitalize">{indices.summary.ndvi_status}</div>
              <div className="mt-1 text-xs text-muted-foreground">santé de la végétation</div>
            </Card>
            <Card className="p-5 border border-border shadow-none">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold flex items-center gap-1">
                <Satellite className="w-3.5 h-3.5" />Sources
              </div>
              <div className="mt-2 space-y-0.5">
                {indices.satellite_sources.map((s) => <div key={s} className="text-xs">{s}</div>)}
              </div>
            </Card>
          </div>

          <Card className="p-5 border border-border shadow-none">
            <h3 className="font-display font-semibold text-lg mb-4">Évolution mensuelle des indices</h3>
            <div style={{ height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={indices.time_series}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(120 10% 88%)" />
                  <XAxis dataKey="month" fontSize={12} />
                  <YAxis fontSize={12} domain={[0, 1]} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="ndvi" name="NDVI (végétation)" stroke="hsl(140 30% 35%)" strokeWidth={2} />
                  <Line type="monotone" dataKey="nbr" name="NBR (incendies)" stroke="hsl(15 70% 50%)" strokeWidth={2} />
                  <Line type="monotone" dataKey="ndwi" name="NDWI (eau)" stroke="hsl(210 60% 45%)" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {landcover && (
            <Card className="p-5 border border-border shadow-none">
              <h3 className="font-display font-semibold text-lg mb-4">Classification de la couverture des sols</h3>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div style={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={landcover.classes} dataKey="percent" nameKey="name" outerRadius={110} label={(e) => `${e.percent.toFixed(0)}%`}>
                        {landcover.classes.map((c, i) => <Cell key={i} fill={c.color} />)}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="space-y-2">
                  {landcover.classes.map((c) => (
                    <div key={c.name} className="flex items-center justify-between p-2 rounded border border-border">
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded" style={{ backgroundColor: c.color }} />
                        <span className="text-sm font-medium">{c.name}</span>
                      </div>
                      <div className="font-display font-semibold">{c.percent}%</div>
                    </div>
                  ))}
                  <div className="text-xs text-muted-foreground mt-3 pt-2 border-t border-border">
                    Source: {landcover.source} · Résolution: {landcover.resolution_m}m
                  </div>
                </div>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
