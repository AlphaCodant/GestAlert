import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import ForestMap from "@/components/ForestMap";
import { Card } from "@/components/ui/card";
import { ALERT_TYPE_LABEL, ALERT_STATUS_LABEL, STATUS_COLOR, fmtDateTime } from "@/lib/constants";
import { Bell, Eye, Plane, Trees, AlertTriangle, ArrowUpRight, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [forests, setForests] = useState([]);
  const [observations, setObservations] = useState([]);
  const [missions, setMissions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [s, a, f, o, m] = await Promise.all([
          api.get("/stats/dashboard"),
          api.get("/alerts"),
          api.get("/forests"),
          api.get("/observations"),
          api.get("/drone-missions"),
        ]);
        setStats(s.data);
        setAlerts(a.data);
        setForests(f.data);
        setObservations(o.data);
        setMissions(m.data);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  const totals = stats?.totals || {};

  const tiles = [
    { l: "Alertes totales", v: totals.alerts ?? 0, sub: `${totals.pending ?? 0} en attente`, i: Bell, c: "text-destructive" },
    { l: "Observations", v: totals.observations ?? 0, sub: "terrain", i: Eye, c: "text-primary" },
    { l: "Missions drone", v: totals.drone_missions ?? 0, sub: "planifiées/terminées", i: Plane, c: "text-sky-700" },
    { l: "Forêts surveillées", v: totals.forests ?? 0, sub: `${(totals.total_area_ha || 0).toLocaleString("fr-FR")} ha`, i: Trees, c: "text-emerald-700" },
  ];

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="dashboard-page">
      <header>
        <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">
          Tableau de bord
        </div>
        <h1 className="font-display font-bold text-3xl lg:text-4xl tracking-tight mt-1">
          Surveillance des forêts classées
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Centre de Gestion de Gagnoa · FC Sangoué & FC Téné
        </p>
      </header>

      {/* KPI Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {tiles.map((t) => (
          <Card
            key={t.l}
            className="p-5 border border-border shadow-none hover:-translate-y-1 hover:shadow-md transition-all"
            data-testid={`kpi-${t.l.toLowerCase().replace(/ /g, "-")}`}
          >
            <div className="flex items-start justify-between">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold">{t.l}</div>
              <t.i className={`w-4 h-4 ${t.c}`} />
            </div>
            <div className="mt-3 font-display text-3xl font-light">{t.v}</div>
            <div className="mt-1 text-xs text-muted-foreground">{t.sub}</div>
          </Card>
        ))}
      </div>

      {/* Map + sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3">
          <Card className="p-4 border border-border shadow-none">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="font-display font-semibold text-lg">Carte SIG temps quasi-réel</h3>
                <p className="text-xs text-muted-foreground">Alertes, observations, missions drone</p>
              </div>
            </div>
            <div style={{ height: 520 }}>
              <ForestMap
                forests={forests}
                alerts={alerts}
                observations={observations}
                missions={missions}
                fit
              />
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          {/* Alertes par statut */}
          <Card className="p-5 border border-border shadow-none">
            <h3 className="font-display font-semibold text-base mb-3">Statuts des alertes</h3>
            <div className="space-y-2">
              {(stats?.alerts_by_status || []).map((s) => (
                <div key={s.status} className="flex items-center justify-between">
                  <span className={`text-xs px-2 py-0.5 rounded border ${STATUS_COLOR[s.status] || ""}`}>
                    {ALERT_STATUS_LABEL[s.status] || s.status}
                  </span>
                  <span className="font-semibold text-sm">{s.count}</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Recent */}
          <Card className="p-5 border border-border shadow-none">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-display font-semibold text-base">Alertes récentes</h3>
              <Link
                to="/dashboard/alerts"
                className="text-xs text-primary hover:underline flex items-center gap-0.5"
                data-testid="see-all-alerts-link"
              >
                Voir tout <ArrowUpRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="space-y-3">
              {(stats?.recent_alerts || []).map((a) => (
                <div key={a.id} className="text-xs border-l-2 border-primary/40 pl-3" data-testid={`recent-alert-${a.id}`}>
                  <div className="flex items-center gap-1.5 font-semibold">
                    <AlertTriangle className="w-3 h-3 text-destructive" />
                    {ALERT_TYPE_LABEL[a.alert_type] || a.alert_type}
                  </div>
                  <div className="text-muted-foreground mt-0.5">{fmtDateTime(a.created_at)}</div>
                </div>
              ))}
              {(!stats?.recent_alerts || stats.recent_alerts.length === 0) && (
                <div className="text-xs text-muted-foreground">Aucune alerte récente</div>
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* Alerts by type */}
      <Card className="p-5 border border-border shadow-none">
        <h3 className="font-display font-semibold text-lg mb-4">Répartition par type d'anomalie</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {(stats?.alerts_by_type || []).map((t) => (
            <div key={t.type} className="bg-muted/40 rounded-md p-3 border border-border">
              <div className="text-xs uppercase tracking-[0.15em] text-muted-foreground font-semibold">
                {ALERT_TYPE_LABEL[t.type] || t.type}
              </div>
              <div className="font-display text-2xl font-bold mt-1.5 text-primary">{t.count}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
