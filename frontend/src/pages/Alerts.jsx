import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "@/components/ui/dialog";
import {
  ALERT_TYPE_LABEL, ALERT_STATUS_LABEL, SEVERITY_LABEL,
  SEVERITY_COLOR, STATUS_COLOR, fmtDateTime,
} from "@/lib/constants";
import { Plus, Loader2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import ForestMap from "@/components/ForestMap";

const TYPES = ["deforestation", "agriculture_illegale", "feu_de_brousse", "exploitation_illegale", "defrichement"];
const SEVERITIES = ["faible", "moyenne", "haute", "critique"];
const STATUSES = ["detectee", "en_verification", "confirmee", "resolue", "rejetee"];

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [forests, setForests] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [statusOpen, setStatusOpen] = useState(false);
  const [selected, setSelected] = useState(null);

  // Create form
  const [form, setForm] = useState({
    forest_id: "", alert_type: "deforestation", severity: "moyenne",
    lat: "", lng: "", area_ha: 1, description: "", source: "satellite",
  });

  // Status update
  const [newStatus, setNewStatus] = useState("en_verification");
  const [statusNote, setStatusNote] = useState("");

  async function load() {
    setLoading(true);
    try {
      const params = filter !== "all" ? { status_filter: filter } : {};
      const [a, f] = await Promise.all([
        api.get("/alerts", { params }),
        api.get("/forests"),
      ]);
      setAlerts(a.data);
      setForests(f.data);
      if (!form.forest_id && f.data.length) setForm((s) => ({ ...s, forest_id: f.data[0].id }));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  async function createAlert(e) {
    e.preventDefault();
    try {
      await api.post("/alerts", {
        ...form,
        lat: parseFloat(form.lat),
        lng: parseFloat(form.lng),
        area_ha: parseFloat(form.area_ha),
      });
      toast.success("Alerte créée");
      setOpen(false);
      setForm((s) => ({ ...s, lat: "", lng: "", description: "", area_ha: 1 }));
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Erreur");
    }
  }

  async function updateStatus() {
    try {
      await api.patch(`/alerts/${selected.id}/status`, { status: newStatus, note: statusNote });
      toast.success("Statut mis à jour");
      setStatusOpen(false);
      setStatusNote("");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Erreur");
    }
  }

  function fillFromForest(forest_id) {
    const f = forests.find((x) => x.id === forest_id);
    setForm((s) => ({
      ...s, forest_id,
      lat: (f.center_lat + (Math.random() - 0.5) * 0.05).toFixed(5),
      lng: (f.center_lng + (Math.random() - 0.5) * 0.05).toFixed(5),
    }));
  }

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="alerts-page">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Module</div>
          <h1 className="font-display font-bold text-3xl lg:text-4xl tracking-tight mt-1">Gestion des alertes</h1>
          <p className="text-sm text-muted-foreground mt-1">Workflow : Détectée → En vérification → Confirmée → Résolue</p>
        </div>
        <div className="flex gap-2">
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-44" data-testid="alerts-filter-select"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous statuts</SelectItem>
              {STATUSES.map((s) => <SelectItem key={s} value={s}>{ALERT_STATUS_LABEL[s]}</SelectItem>)}
            </SelectContent>
          </Select>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button data-testid="create-alert-btn"><Plus className="w-4 h-4 mr-2" />Nouvelle alerte</Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader><DialogTitle>Nouvelle alerte</DialogTitle></DialogHeader>
              <form onSubmit={createAlert} className="space-y-3">
                <div>
                  <Label>Forêt</Label>
                  <Select value={form.forest_id} onValueChange={fillFromForest}>
                    <SelectTrigger data-testid="alert-forest-select"><SelectValue placeholder="Choisir" /></SelectTrigger>
                    <SelectContent>
                      {forests.map((f) => <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Type</Label>
                    <Select value={form.alert_type} onValueChange={(v) => setForm({ ...form, alert_type: v })}>
                      <SelectTrigger data-testid="alert-type-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{TYPES.map((t) => <SelectItem key={t} value={t}>{ALERT_TYPE_LABEL[t]}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Sévérité</Label>
                    <Select value={form.severity} onValueChange={(v) => setForm({ ...form, severity: v })}>
                      <SelectTrigger data-testid="alert-severity-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{SEVERITIES.map((s) => <SelectItem key={s} value={s}>{SEVERITY_LABEL[s]}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Latitude</Label>
                    <Input value={form.lat} onChange={(e) => setForm({ ...form, lat: e.target.value })} required data-testid="alert-lat-input" />
                  </div>
                  <div>
                    <Label>Longitude</Label>
                    <Input value={form.lng} onChange={(e) => setForm({ ...form, lng: e.target.value })} required data-testid="alert-lng-input" />
                  </div>
                  <div>
                    <Label>Surface (ha)</Label>
                    <Input type="number" step="0.1" value={form.area_ha} onChange={(e) => setForm({ ...form, area_ha: e.target.value })} required data-testid="alert-area-input" />
                  </div>
                  <div>
                    <Label>Source</Label>
                    <Select value={form.source} onValueChange={(v) => setForm({ ...form, source: v })}>
                      <SelectTrigger data-testid="alert-source-select"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="satellite">Satellite</SelectItem>
                        <SelectItem value="drone">Drone</SelectItem>
                        <SelectItem value="terrain">Terrain</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label>Description</Label>
                  <Textarea required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="alert-description-input" />
                </div>
                <DialogFooter>
                  <Button type="submit" data-testid="alert-submit-btn">Créer</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </header>

      <Card className="p-4 border border-border shadow-none">
        <div style={{ height: 360 }}>
          <ForestMap forests={forests} alerts={alerts} fit />
        </div>
      </Card>

      <Card className="border border-border shadow-none overflow-hidden">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-12 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
          ) : alerts.length === 0 ? (
            <div className="p-12 text-center text-muted-foreground">Aucune alerte</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left p-3 font-semibold">Type</th>
                  <th className="text-left p-3 font-semibold">Sévérité</th>
                  <th className="text-left p-3 font-semibold">Statut</th>
                  <th className="text-left p-3 font-semibold">Surface</th>
                  <th className="text-left p-3 font-semibold">Source</th>
                  <th className="text-left p-3 font-semibold">Détectée</th>
                  <th className="text-right p-3 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id} className="border-b border-border hover:bg-muted/20" data-testid={`alert-row-${a.id}`}>
                    <td className="p-3 font-medium">
                      <div className="flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 text-destructive" />
                        {ALERT_TYPE_LABEL[a.alert_type] || a.alert_type}
                      </div>
                    </td>
                    <td className="p-3"><span className={`text-xs px-2 py-0.5 rounded border ${SEVERITY_COLOR[a.severity]}`}>{SEVERITY_LABEL[a.severity]}</span></td>
                    <td className="p-3"><span className={`text-xs px-2 py-0.5 rounded border ${STATUS_COLOR[a.status]}`}>{ALERT_STATUS_LABEL[a.status]}</span></td>
                    <td className="p-3">{a.area_ha} ha</td>
                    <td className="p-3 capitalize">{a.source}</td>
                    <td className="p-3 text-xs text-muted-foreground">{fmtDateTime(a.created_at)}</td>
                    <td className="p-3 text-right">
                      <Button
                        size="sm" variant="outline"
                        onClick={() => { setSelected(a); setNewStatus(a.status); setStatusOpen(true); }}
                        data-testid={`update-status-btn-${a.id}`}
                      >
                        Mettre à jour
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>

      {/* Status update dialog */}
      <Dialog open={statusOpen} onOpenChange={setStatusOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Modifier le statut de l'alerte</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Nouveau statut</Label>
              <Select value={newStatus} onValueChange={setNewStatus}>
                <SelectTrigger data-testid="new-status-select"><SelectValue /></SelectTrigger>
                <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{ALERT_STATUS_LABEL[s]}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label>Note (optionnel)</Label>
              <Textarea value={statusNote} onChange={(e) => setStatusNote(e.target.value)} data-testid="status-note-input" />
            </div>
            {selected?.history?.length > 0 && (
              <div>
                <Label>Historique</Label>
                <div className="mt-2 space-y-1.5 max-h-40 overflow-auto">
                  {selected.history.map((h, i) => (
                    <div key={i} className="text-xs border-l-2 border-primary/30 pl-2">
                      <div className="font-semibold">{ALERT_STATUS_LABEL[h.status]}</div>
                      <div className="text-muted-foreground">{fmtDateTime(h.at)} · {h.by}</div>
                      {h.note && <div className="italic">{h.note}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button onClick={updateStatus} data-testid="confirm-status-btn">Confirmer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
