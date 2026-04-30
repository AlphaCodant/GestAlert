import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Plus, Eye, Loader2, MapPin } from "lucide-react";
import { toast } from "sonner";
import { ALERT_TYPE_LABEL, fmtDateTime } from "@/lib/constants";
import ForestMap from "@/components/ForestMap";

const TYPES = ["deforestation", "agriculture_illegale", "feu_de_brousse", "exploitation_illegale", "defrichement", "autre"];

export default function Observations() {
  const [observations, setObservations] = useState([]);
  const [forests, setForests] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    forest_id: "", observation_type: "deforestation", lat: "", lng: "", description: "", photo_url: "",
  });

  async function load() {
    setLoading(true);
    try {
      const [o, f] = await Promise.all([api.get("/observations"), api.get("/forests")]);
      setObservations(o.data);
      setForests(f.data);
      if (!form.forest_id && f.data.length) setForm((s) => ({ ...s, forest_id: f.data[0].id }));
    } finally { setLoading(false); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  function geolocate() {
    if (!navigator.geolocation) {
      toast.error("Géolocalisation non disponible");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setForm((s) => ({ ...s, lat: pos.coords.latitude.toFixed(5), lng: pos.coords.longitude.toFixed(5) })),
      () => toast.error("Impossible d'obtenir la position")
    );
  }

  async function submit(e) {
    e.preventDefault();
    try {
      await api.post("/observations", {
        ...form,
        lat: parseFloat(form.lat),
        lng: parseFloat(form.lng),
        photo_url: form.photo_url || null,
      });
      toast.success("Observation enregistrée");
      setOpen(false);
      setForm((s) => ({ ...s, lat: "", lng: "", description: "", photo_url: "" }));
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Erreur");
    }
  }

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="observations-page">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Module</div>
          <h1 className="font-display font-bold text-3xl lg:text-4xl tracking-tight mt-1">Observations terrain</h1>
          <p className="text-sm text-muted-foreground mt-1">Données collectées par les agents forestiers sur le terrain</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button data-testid="create-observation-btn"><Plus className="w-4 h-4 mr-2" />Nouvelle observation</Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle>Nouvelle observation</DialogTitle></DialogHeader>
            <form onSubmit={submit} className="space-y-3">
              <div>
                <Label>Forêt</Label>
                <Select value={form.forest_id} onValueChange={(v) => setForm({ ...form, forest_id: v })}>
                  <SelectTrigger data-testid="obs-forest-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{forests.map((f) => <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label>Type</Label>
                <Select value={form.observation_type} onValueChange={(v) => setForm({ ...form, observation_type: v })}>
                  <SelectTrigger data-testid="obs-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{TYPES.map((t) => <SelectItem key={t} value={t}>{ALERT_TYPE_LABEL[t]}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Latitude</Label>
                  <Input value={form.lat} onChange={(e) => setForm({ ...form, lat: e.target.value })} required data-testid="obs-lat-input" />
                </div>
                <div>
                  <Label>Longitude</Label>
                  <Input value={form.lng} onChange={(e) => setForm({ ...form, lng: e.target.value })} required data-testid="obs-lng-input" />
                </div>
              </div>
              <Button type="button" variant="outline" onClick={geolocate} data-testid="obs-geolocate-btn">
                <MapPin className="w-4 h-4 mr-2" />Utiliser ma position
              </Button>
              <div>
                <Label>Description</Label>
                <Textarea required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="obs-description-input" />
              </div>
              <div>
                <Label>Photo (URL, optionnel)</Label>
                <Input value={form.photo_url} onChange={(e) => setForm({ ...form, photo_url: e.target.value })} placeholder="https://..." data-testid="obs-photo-input" />
              </div>
              <DialogFooter><Button type="submit" data-testid="obs-submit-btn">Enregistrer</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </header>

      <Card className="p-4 border border-border shadow-none">
        <div style={{ height: 320 }}>
          <ForestMap forests={forests} observations={observations} fit />
        </div>
      </Card>

      {loading ? (
        <Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {observations.map((o) => (
            <Card key={o.id} className="p-5 border border-border shadow-none hover:-translate-y-1 hover:shadow-md transition-all" data-testid={`obs-card-${o.id}`}>
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold">
                <Eye className="w-3.5 h-3.5" />
                {ALERT_TYPE_LABEL[o.observation_type]}
              </div>
              <p className="mt-3 text-sm leading-relaxed">{o.description}</p>
              <div className="mt-4 pt-3 border-t border-border text-xs text-muted-foreground">
                <div>par <span className="font-medium text-foreground">{o.agent_name}</span></div>
                <div>{fmtDateTime(o.created_at)}</div>
                <div className="font-mono mt-1">{o.lat?.toFixed(4)}, {o.lng?.toFixed(4)}</div>
              </div>
            </Card>
          ))}
          {observations.length === 0 && <div className="col-span-full text-center text-muted-foreground py-12">Aucune observation</div>}
        </div>
      )}
    </div>
  );
}
