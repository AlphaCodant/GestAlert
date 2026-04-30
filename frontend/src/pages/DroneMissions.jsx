import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Plus, Plane, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { MISSION_STATUS_LABEL, MISSION_STATUS_COLOR, fmtDateTime } from "@/lib/constants";
import ForestMap from "@/components/ForestMap";

const STATUSES = ["planifiee", "en_cours", "terminee", "annulee"];

export default function DroneMissions() {
  const [missions, setMissions] = useState([]);
  const [forests, setForests] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [updateOpen, setUpdateOpen] = useState(false);
  const [selected, setSelected] = useState(null);
  const [statusUpd, setStatusUpd] = useState("");
  const [notes, setNotes] = useState("");

  const [form, setForm] = useState({
    forest_id: "", planned_date: "", target_lat: "", target_lng: "", radius_m: 500, purpose: "",
  });

  async function load() {
    setLoading(true);
    try {
      const [m, f] = await Promise.all([api.get("/drone-missions"), api.get("/forests")]);
      setMissions(m.data);
      setForests(f.data);
      if (!form.forest_id && f.data.length) setForm((s) => ({ ...s, forest_id: f.data[0].id }));
    } finally { setLoading(false); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function submit(e) {
    e.preventDefault();
    try {
      await api.post("/drone-missions", {
        ...form,
        target_lat: parseFloat(form.target_lat),
        target_lng: parseFloat(form.target_lng),
        radius_m: parseFloat(form.radius_m),
        planned_date: new Date(form.planned_date).toISOString(),
      });
      toast.success("Mission planifiée");
      setOpen(false);
      setForm((s) => ({ ...s, planned_date: "", target_lat: "", target_lng: "", purpose: "" }));
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Erreur"); }
  }

  async function updateMission() {
    try {
      await api.patch(`/drone-missions/${selected.id}`, { status: statusUpd, notes });
      toast.success("Mission mise à jour");
      setUpdateOpen(false);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Erreur"); }
  }

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="drones-page">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Module</div>
          <h1 className="font-display font-bold text-3xl lg:text-4xl tracking-tight mt-1">Missions drone</h1>
          <p className="text-sm text-muted-foreground mt-1">Planification & suivi des survols DJI Mavic 3 Multispectral</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button data-testid="create-mission-btn"><Plus className="w-4 h-4 mr-2" />Nouvelle mission</Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle>Planifier une mission drone</DialogTitle></DialogHeader>
            <form onSubmit={submit} className="space-y-3">
              <div>
                <Label>Forêt</Label>
                <Select value={form.forest_id} onValueChange={(v) => setForm({ ...form, forest_id: v })}>
                  <SelectTrigger data-testid="mission-forest-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{forests.map((f) => <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label>Date prévue</Label>
                <Input type="datetime-local" required value={form.planned_date} onChange={(e) => setForm({ ...form, planned_date: e.target.value })} data-testid="mission-date-input" />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label>Lat. cible</Label>
                  <Input value={form.target_lat} onChange={(e) => setForm({ ...form, target_lat: e.target.value })} required data-testid="mission-lat-input" />
                </div>
                <div>
                  <Label>Lng. cible</Label>
                  <Input value={form.target_lng} onChange={(e) => setForm({ ...form, target_lng: e.target.value })} required data-testid="mission-lng-input" />
                </div>
                <div>
                  <Label>Rayon (m)</Label>
                  <Input type="number" value={form.radius_m} onChange={(e) => setForm({ ...form, radius_m: e.target.value })} required data-testid="mission-radius-input" />
                </div>
              </div>
              <div>
                <Label>Objectif</Label>
                <Textarea required value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} placeholder="Ex: Vérification d'alerte, cartographie, suivi NDVI..." data-testid="mission-purpose-input" />
              </div>
              <DialogFooter><Button type="submit" data-testid="mission-submit-btn">Planifier</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </header>

      <Card className="p-4 border border-border shadow-none">
        <div style={{ height: 320 }}>
          <ForestMap forests={forests} missions={missions} fit />
        </div>
      </Card>

      {loading ? (
        <Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {missions.map((m) => (
            <Card key={m.id} className="p-5 border border-border shadow-none hover:-translate-y-1 hover:shadow-md transition-all" data-testid={`mission-card-${m.id}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold">
                  <Plane className="w-3.5 h-3.5" />Mission
                </div>
                <span className={`text-xs px-2 py-0.5 rounded border ${MISSION_STATUS_COLOR[m.status]}`}>
                  {MISSION_STATUS_LABEL[m.status]}
                </span>
              </div>
              <p className="mt-3 text-sm leading-relaxed font-medium">{m.purpose}</p>
              <div className="mt-3 text-xs text-muted-foreground space-y-1">
                <div>Date prévue: <span className="text-foreground">{fmtDateTime(m.planned_date)}</span></div>
                <div className="font-mono">{m.target_lat?.toFixed(4)}, {m.target_lng?.toFixed(4)} · rayon {m.radius_m}m</div>
                {m.ndvi_avg && <div>NDVI moyen: <span className="text-primary font-semibold">{m.ndvi_avg}</span></div>}
              </div>
              <Button
                size="sm" variant="outline" className="w-full mt-4"
                onClick={() => { setSelected(m); setStatusUpd(m.status); setNotes(m.notes || ""); setUpdateOpen(true); }}
                data-testid={`mission-update-btn-${m.id}`}
              >Mettre à jour</Button>
            </Card>
          ))}
          {missions.length === 0 && <div className="col-span-full text-center text-muted-foreground py-12">Aucune mission</div>}
        </div>
      )}

      <Dialog open={updateOpen} onOpenChange={setUpdateOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Mettre à jour la mission</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Statut</Label>
              <Select value={statusUpd} onValueChange={setStatusUpd}>
                <SelectTrigger data-testid="mission-status-select"><SelectValue /></SelectTrigger>
                <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{MISSION_STATUS_LABEL[s]}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label>Notes</Label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="mission-notes-input" />
            </div>
          </div>
          <DialogFooter><Button onClick={updateMission} data-testid="mission-confirm-update">Enregistrer</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
