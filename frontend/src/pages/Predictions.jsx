import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Sparkles, AlertTriangle } from "lucide-react";
import ForestMap from "@/components/ForestMap";

export default function Predictions() {
  const [forests, setForests] = useState([]);
  const [forestId, setForestId] = useState("");
  const [data, setData] = useState(null);
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
    api.get(`/predictions/${forestId}`).then((r) => setData(r.data)).finally(() => setLoading(false));
  }, [forestId]);

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="predictions-page">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Module IA</div>
          <h1 className="font-display font-bold text-3xl lg:text-4xl tracking-tight mt-1">Prédictions de déforestation</h1>
          <p className="text-sm text-muted-foreground mt-1">Carte de probabilité à 90 jours · Random Forest + Logistic Regression</p>
        </div>
        <Select value={forestId} onValueChange={setForestId}>
          <SelectTrigger className="w-72" data-testid="predictions-forest-select"><SelectValue /></SelectTrigger>
          <SelectContent>{forests.map((f) => <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>)}</SelectContent>
        </Select>
      </header>

      {loading || !data ? (
        <Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <div className="lg:col-span-3">
            <Card className="p-4 border border-border shadow-none">
              <div style={{ height: 540 }}>
                <ForestMap
                  center={[data.forest.center_lat, data.forest.center_lng]}
                  zoom={11}
                  forests={[data.forest]}
                  riskCells={data.cells}
                />
              </div>
            </Card>
          </div>
          <div className="space-y-4">
            <Card className="p-5 border border-border shadow-none">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold">Modèle</div>
              <p className="text-sm mt-2">{data.model}</p>
              <div className="mt-3 pt-3 border-t border-border">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold">Horizon</div>
                <p className="text-sm mt-1">{data.horizon_days} jours</p>
              </div>
            </Card>
            <Card className="p-5 border border-border shadow-none">
              <div className="flex items-center gap-2 text-destructive font-semibold">
                <AlertTriangle className="w-4 h-4" />
                Zones à haut risque
              </div>
              <div className="font-display text-4xl font-bold text-destructive mt-2">{data.high_risk_count}</div>
              <p className="text-xs text-muted-foreground">cellules avec risque ≥ 70%</p>
            </Card>
            <Card className="p-5 border border-border shadow-none">
              <div className="flex items-center gap-2 text-primary font-semibold">
                <Sparkles className="w-4 h-4" />Top 5 zones critiques
              </div>
              <div className="mt-3 space-y-2">
                {(data.high_risk_zones || []).slice(0, 5).map((z, i) => (
                  <div key={i} className="text-xs border-l-2 border-destructive pl-2 font-mono">
                    {z.lat.toFixed(4)}, {z.lng.toFixed(4)} <span className="text-destructive font-bold ml-1">{(z.risk * 100).toFixed(0)}%</span>
                  </div>
                ))}
                {(!data.high_risk_zones || data.high_risk_zones.length === 0) && <p className="text-xs text-muted-foreground">Aucune zone critique</p>}
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
