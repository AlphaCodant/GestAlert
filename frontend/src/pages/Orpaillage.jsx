import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  DETECTION_STATUS_LABEL, DETECTION_STATUS_COLOR, DETECTION_LEVEL_COLOR, fmtDateTime,
} from "@/lib/constants";
import {
  Satellite, Loader2, Plus, Download, Upload, Play, AlertTriangle, Plane, BellPlus, Info, SlidersHorizontal, MapPinned,
} from "lucide-react";
import { toast } from "sonner";
import OrpaillageMap from "@/components/OrpaillageMap";

const STATUSES = ["presume", "precise", "confirme", "infirme"];
const RUN_STATUS = { en_cours: "En cours", terminee: "Terminée", echec: "Échec" };

function isoDay(d) {
  return d.toISOString().slice(0, 10);
}

function defaultPeriods() {
  // Période récente : les 120 derniers jours. Référence : la même fenêtre un an plus tôt,
  // pour comparer des saisons identiques et limiter les fausses alertes liées à la phénologie.
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - 120);
  const refEnd = new Date(end);
  refEnd.setFullYear(refEnd.getFullYear() - 1);
  const refStart = new Date(start);
  refStart.setFullYear(refStart.getFullYear() - 1);
  return { ref_start: isoDay(refStart), ref_end: isoDay(refEnd), recent_start: isoDay(start), recent_end: isoDay(end) };
}

function errMsg(e) {
  return formatApiErrorDetail(e?.response?.data?.detail) || "Erreur";
}

function Stat({ label, value, sub, tone }) {
  return (
    <Card className="p-4 border border-border shadow-none">
      <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground font-semibold">{label}</div>
      <div className={`mt-1.5 font-display text-3xl font-semibold ${tone || "text-foreground"}`}>{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
    </Card>
  );
}

export default function Orpaillage() {
  const { user } = useAuth();
  const canAnalyse = user?.role === "admin" || user?.role === "analyste_sig";

  const [config, setConfig] = useState(null);
  const [zones, setZones] = useState([]);
  const [zoneId, setZoneId] = useState("");
  const [detections, setDetections] = useState([]);
  const [runs, setRuns] = useState([]);
  const [sites, setSites] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [levelFilter, setLevelFilter] = useState("all");

  const [periods, setPeriods] = useState(defaultPeriods);
  const [params, setParams] = useState(null);
  const [showParams, setShowParams] = useState(false);
  const [launching, setLaunching] = useState(false);

  const [zoneOpen, setZoneOpen] = useState(false);
  const [zoneForm, setZoneForm] = useState({ name: "", description: "", min_lat: "", min_lng: "", max_lat: "", max_lng: "" });
  const [zoneGeo, setZoneGeo] = useState(null);

  const [statusOpen, setStatusOpen] = useState(false);
  const [newStatus, setNewStatus] = useState("precise");
  const [statusNote, setStatusNote] = useState("");

  const [missionOpen, setMissionOpen] = useState(false);
  const [missionDate, setMissionDate] = useState(isoDay(new Date(Date.now() + 3 * 864e5)));

  const siteInput = useRef(null);
  const zone = useMemo(() => zones.find((z) => z.id === zoneId), [zones, zoneId]);
  const runningRun = runs.find((r) => r.status === "en_cours");

  useEffect(() => {
    (async () => {
      try {
        const [c, z] = await Promise.all([api.get("/orpaillage/config"), api.get("/orpaillage/zones")]);
        setConfig(c.data);
        setParams(c.data.default_params);
        setZones(z.data);
        if (z.data.length) setZoneId(z.data[z.data.length - 1].id);
      } catch (e) {
        toast.error(errMsg(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const loadZoneData = useCallback(async () => {
    if (!zoneId) return;
    const filters = { zone_id: zoneId };
    if (statusFilter !== "all") filters.status = statusFilter;
    if (levelFilter !== "all") filters.level = levelFilter;
    const [d, r, s, st] = await Promise.all([
      api.get("/orpaillage/detections", { params: filters }),
      api.get("/orpaillage/runs", { params: { zone_id: zoneId } }),
      api.get("/orpaillage/known-sites"),
      api.get("/orpaillage/stats", { params: { zone_id: zoneId } }),
    ]);
    setDetections(d.data);
    setRuns(r.data);
    setSites(s.data);
    setStats(st.data);
    setSelected((cur) => (cur ? d.data.find((x) => x.id === cur.id) || null : null));
  }, [zoneId, statusFilter, levelFilter]);

  useEffect(() => {
    loadZoneData().catch((e) => toast.error(errMsg(e)));
  }, [loadZoneData]);

  // Suivi d'une analyse en cours
  useEffect(() => {
    if (!runningRun) return;
    const t = setInterval(async () => {
      try {
        const r = await api.get(`/orpaillage/runs/${runningRun.id}`);
        if (r.data.status !== "en_cours") {
          clearInterval(t);
          if (r.data.status === "terminee") toast.success(`Analyse terminée : ${r.data.detections_count} nouvelle(s) zone(s) suspecte(s)`);
          else toast.error(`Analyse en échec : ${r.data.error || "erreur inconnue"}`);
          loadZoneData();
        }
      } catch {
        /* nouvelle tentative au prochain intervalle */
      }
    }, 3000);
    return () => clearInterval(t);
  }, [runningRun, loadZoneData]);

  async function launchRun() {
    setLaunching(true);
    try {
      await api.post("/orpaillage/runs", { zone_id: zoneId, ...periods, params });
      toast.info("Analyse lancée");
      await loadZoneData();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setLaunching(false);
    }
  }

  async function checkGee() {
    try {
      const r = await api.get("/orpaillage/gee-check");
      toast.success(`Google Earth Engine connecté : ${r.data.sentinel2_images_gagnoa_jan_fev_2026} images Sentinel-2 trouvées sur Gagnoa (janv.-févr. 2026)`);
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  async function createZone(e) {
    e.preventDefault();
    const body = { name: zoneForm.name, description: zoneForm.description };
    if (zoneGeo) body.geometry = zoneGeo;
    else ["min_lat", "min_lng", "max_lat", "max_lng"].forEach((k) => { body[k] = parseFloat(String(zoneForm[k]).replace(",", ".")); });
    try {
      const r = await api.post("/orpaillage/zones", body);
      setZones((zs) => [...zs, r.data]);
      setZoneId(r.data.id);
      setZoneOpen(false);
      setZoneGeo(null);
      setZoneForm({ name: "", description: "", min_lat: "", min_lng: "", max_lat: "", max_lng: "" });
      toast.success("Zone créée");
    } catch (e2) {
      toast.error(errMsg(e2));
    }
  }

  async function readZoneFile(file) {
    if (!file) return;
    try {
      setZoneGeo(JSON.parse(await file.text()));
      if (!zoneForm.name) setZoneForm((s) => ({ ...s, name: file.name.replace(/\.(geo)?json$/i, "") }));
    } catch {
      toast.error("Fichier GeoJSON illisible");
    }
  }

  async function importSites(file) {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.post("/orpaillage/known-sites/import", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`${r.data.imported} site(s) connu(s) importé(s)`);
      if (r.data.errors.length) toast.warning(`${r.data.errors.length} ligne(s) ignorée(s) : ${r.data.errors[0]}`);
      loadZoneData();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      if (siteInput.current) siteInput.current.value = "";
    }
  }

  async function exportAs(format) {
    try {
      const p = { format, zone_id: zoneId };
      if (statusFilter !== "all") p.status = statusFilter;
      if (levelFilter !== "all") p.level = levelFilter;
      const r = await api.get("/orpaillage/export", { params: p, responseType: "blob" });
      const name = /filename="([^"]+)"/.exec(r.headers["content-disposition"] || "")?.[1] || `orpaillage.${format}`;
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error("Export impossible");
    }
  }

  async function saveStatus() {
    try {
      await api.patch(`/orpaillage/detections/${selected.id}/status`, { status: newStatus, note: statusNote });
      toast.success("Statut mis à jour");
      setStatusOpen(false);
      setStatusNote("");
      loadZoneData();
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  async function createAlert(d) {
    try {
      await api.post(`/orpaillage/detections/${d.id}/alert`);
      toast.success(`Alerte créée pour ${d.code}`);
      loadZoneData();
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  async function createMission() {
    try {
      await api.post(`/orpaillage/detections/${selected.id}/drone-mission`, { planned_date: missionDate });
      toast.success(`Mission drone planifiée sur ${selected.code}`);
      setMissionOpen(false);
      loadZoneData();
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  if (loading) return <Loader2 className="w-6 h-6 animate-spin text-primary mx-auto mt-24" />;

  const simulation = config && !config.gee_configured;

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="orpaillage-page">
      <header className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Lutte contre l'orpaillage clandestin · Gôh</div>
          <h1 className="font-display font-bold text-3xl lg:text-4xl tracking-tight mt-1">Détection satellitaire des sites d'orpaillage</h1>
          <p className="text-sm text-muted-foreground mt-1">Sentinel-2 · perte de végétation, sol nu, eau turbide, proximité des cours d'eau</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Select value={zoneId} onValueChange={(v) => { setZoneId(v); setSelected(null); }}>
            <SelectTrigger className="w-64" data-testid="zone-select"><SelectValue placeholder="Choisir une zone" /></SelectTrigger>
            <SelectContent>{zones.map((z) => <SelectItem key={z.id} value={z.id}>{z.name}</SelectItem>)}</SelectContent>
          </Select>
          {canAnalyse && (
            <Button variant="outline" onClick={() => setZoneOpen(true)} data-testid="new-zone-btn">
              <Plus className="w-4 h-4 mr-2" />Nouvelle zone
            </Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" disabled={!detections.length} data-testid="export-btn"><Download className="w-4 h-4 mr-2" />Exporter</Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => exportAs("gpx")}>GPX (GPS Garmin)</DropdownMenuItem>
              <DropdownMenuItem onClick={() => exportAs("kml")}>KML (Google Earth)</DropdownMenuItem>
              <DropdownMenuItem onClick={() => exportAs("geojson")}>GeoJSON (QGIS)</DropdownMenuItem>
              <DropdownMenuItem onClick={() => exportAs("csv")}>CSV (Excel)</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {simulation && (
        <div className="flex gap-3 items-start rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900" data-testid="simulation-banner">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">Mode démonstration.</span> Google Earth Engine n'est pas configuré sur le serveur :
            les analyses produisent des zones <span className="font-semibold">fictives</span>, sans valeur opérationnelle.
            Renseignez GEE_PRIVATE_KEY_FILE (ou GEE_SERVICE_ACCOUNT_JSON) dans backend/.env pour analyser les vraies images Sentinel-2.
          </div>
        </div>
      )}
      {zone?.approximate && (
        <div className="flex gap-3 items-start rounded-lg border border-border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
          <Info className="w-4 h-4 mt-0.5 shrink-0" />
          <div>{zone.description}</div>
        </div>
      )}

      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <Stat label="Zones suspectes" value={stats.total} sub={`${stats.area_ha} ha au total`} />
          <Stat label="Suspicion forte" value={stats.by_level.forte} tone="text-red-700" sub="score ≥ 70 %" />
          <Stat label="À vérifier" value={stats.by_status.presume + stats.by_status.precise} sub="présumées ou précisées" />
          <Stat label="Confirmées terrain" value={stats.by_status.confirme} tone="text-red-700" sub={`${stats.area_confirmed_ha} ha`} />
          <Stat
            label="Taux de confirmation"
            value={stats.confirmation_rate == null ? "—" : `${Math.round(stats.confirmation_rate * 100)} %`}
            sub={`${stats.by_status.confirme + stats.by_status.infirme} zone(s) contrôlée(s)`}
          />
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2 p-3 border border-border shadow-none">
          <div style={{ height: 560 }}>
            <OrpaillageMap zone={zone} detections={detections} sites={sites} selected={selected} onSelect={setSelected} />
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-1 px-1 pt-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-red-600/60 border border-red-600" />Suspicion forte</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-amber-500/60 border border-amber-500" />Moyenne</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-lime-500/60 border border-lime-500" />Faible</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-sky-400 border-2 border-slate-900" />Site connu</span>
            <span>Contour pointillé : présumé · plein : précisé ou confirmé · gris : infirmé</span>
          </div>
        </Card>

        <div className="space-y-4">
          {selected ? (
            <Card className="p-5 border border-border shadow-none" data-testid="detection-detail">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-mono font-bold text-lg">{selected.code}</div>
                  <div className="text-xs text-muted-foreground font-mono">{selected.lat.toFixed(5)}, {selected.lng.toFixed(5)}</div>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full border ${DETECTION_STATUS_COLOR[selected.status]}`}>
                  {DETECTION_STATUS_LABEL[selected.status]}
                </span>
              </div>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-sm mt-4">
                <dt className="text-muted-foreground">Score</dt>
                <dd className="font-semibold">{Math.round(selected.score * 100)} % ({selected.level})</dd>
                <dt className="text-muted-foreground">Surface</dt><dd>{selected.area_ha} ha</dd>
                <dt className="text-muted-foreground">Perte de végétation</dt><dd>{selected.indices.dndvi ?? "—"} (ΔNDVI)</dd>
                <dt className="text-muted-foreground">Sol nu</dt><dd>{selected.indices.bsi ?? "—"} (BSI)</dd>
                <dt className="text-muted-foreground">Turbidité</dt><dd>{selected.indices.ndti ?? "—"} (NDTI)</dd>
                <dt className="text-muted-foreground">Cours d'eau</dt>
                <dd>{selected.indices.dist_water_m == null ? "—" : `${Math.round(selected.indices.dist_water_m)} m`}</dd>
                <dt className="text-muted-foreground">Site connu</dt>
                <dd>{selected.known_site_id ? `à ${Math.round(selected.known_site_distance_m)} m` : "aucun à proximité"}</dd>
              </dl>
              <div className="flex flex-wrap gap-2 mt-4">
                <Button size="sm" onClick={() => { setNewStatus(selected.status === "presume" ? "precise" : "confirme"); setStatusOpen(true); }} data-testid="change-status-btn">
                  Changer le statut
                </Button>
                <Button size="sm" variant="outline" onClick={() => setMissionOpen(true)} disabled={!!selected.mission_id}>
                  <Plane className="w-4 h-4 mr-1.5" />{selected.mission_id ? "Mission planifiée" : "Mission drone"}
                </Button>
                <Button size="sm" variant="outline" onClick={() => createAlert(selected)} disabled={!!selected.alert_id}>
                  <BellPlus className="w-4 h-4 mr-1.5" />{selected.alert_id ? "Alerte créée" : "Créer une alerte"}
                </Button>
              </div>
              <div className="mt-4 pt-3 border-t border-border space-y-2 max-h-40 overflow-y-auto">
                {[...selected.history].reverse().map((h, i) => (
                  <div key={i} className="text-xs border-l-2 border-primary/40 pl-2">
                    <div className="font-medium">{DETECTION_STATUS_LABEL[h.status] || h.status} · {h.by}</div>
                    <div className="text-muted-foreground">{fmtDateTime(h.at)}{h.note ? ` — ${h.note}` : ""}</div>
                  </div>
                ))}
              </div>
            </Card>
          ) : (
            <Card className="p-5 border border-dashed border-border shadow-none text-sm text-muted-foreground flex gap-3">
              <MapPinned className="w-5 h-5 shrink-0 text-primary" />
              Cliquez sur une zone de la carte ou du tableau pour voir ses indicateurs, changer son statut ou planifier une vérification.
            </Card>
          )}

          {canAnalyse && params && (
            <Card className="p-5 border border-border shadow-none" data-testid="run-card">
              <div className="flex items-center gap-2 font-semibold"><Satellite className="w-4 h-4 text-primary" />Nouvelle analyse</div>
              <p className="text-xs text-muted-foreground mt-1">Compare une période de référence à une période récente.</p>
              {config?.gee_identity && (
                <div className="mt-2 flex items-center justify-between gap-2 rounded-md bg-emerald-50 border border-emerald-200 px-2.5 py-1.5 text-xs text-emerald-900">
                  <span className="truncate">GEE · projet {config.gee_identity.project}</span>
                  <button type="button" className="font-semibold underline shrink-0" onClick={checkGee}>Tester</button>
                </div>
              )}
              <div className="grid grid-cols-2 gap-2 mt-3">
                <div><Label className="text-xs">Référence : début</Label><Input type="date" value={periods.ref_start} onChange={(e) => setPeriods({ ...periods, ref_start: e.target.value })} /></div>
                <div><Label className="text-xs">Référence : fin</Label><Input type="date" value={periods.ref_end} onChange={(e) => setPeriods({ ...periods, ref_end: e.target.value })} /></div>
                <div><Label className="text-xs">Récente : début</Label><Input type="date" value={periods.recent_start} onChange={(e) => setPeriods({ ...periods, recent_start: e.target.value })} /></div>
                <div><Label className="text-xs">Récente : fin</Label><Input type="date" value={periods.recent_end} onChange={(e) => setPeriods({ ...periods, recent_end: e.target.value })} /></div>
              </div>
              <button type="button" className="flex items-center gap-1.5 text-xs text-primary mt-3" onClick={() => setShowParams(!showParams)}>
                <SlidersHorizontal className="w-3.5 h-3.5" />{showParams ? "Masquer les seuils" : "Ajuster les seuils"}
              </button>
              {showParams && (
                <div className="grid grid-cols-2 gap-2 mt-2">
                  {[
                    ["dndvi_min", "Perte NDVI min.", 0.05],
                    ["bsi_min", "Sol nu (BSI) min.", 0.01],
                    ["min_area_ha", "Surface min. (ha)", 0.1],
                    ["max_cloud", "Nuages max. (%)", 5],
                    ["water_buffer_m", "Rayon cours d'eau (m)", 100],
                    ["known_site_radius_m", "Rayon site connu (m)", 50],
                  ].map(([k, label, step]) => (
                    <div key={k}>
                      <Label className="text-xs">{label}</Label>
                      <Input type="number" step={step} value={params[k]} onChange={(e) => setParams({ ...params, [k]: parseFloat(e.target.value) })} />
                    </div>
                  ))}
                </div>
              )}
              <Button className="w-full mt-4" onClick={launchRun} disabled={!zoneId || launching || !!runningRun} data-testid="launch-run-btn">
                {runningRun || launching ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
                {runningRun ? "Analyse en cours…" : simulation ? "Lancer (démonstration)" : "Lancer l'analyse"}
              </Button>
            </Card>
          )}
        </div>
      </div>

      <Tabs defaultValue="detections">
        <TabsList>
          <TabsTrigger value="detections">Zones suspectes ({detections.length})</TabsTrigger>
          <TabsTrigger value="runs">Analyses ({runs.length})</TabsTrigger>
          <TabsTrigger value="sites">Sites connus ({sites.length})</TabsTrigger>
          <TabsTrigger value="method">Méthode</TabsTrigger>
        </TabsList>

        <TabsContent value="detections">
          <Card className="border border-border shadow-none">
            <div className="flex flex-wrap gap-2 p-3 border-b border-border">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tous les statuts</SelectItem>
                  {STATUSES.map((s) => <SelectItem key={s} value={s}>{DETECTION_STATUS_LABEL[s]}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={levelFilter} onValueChange={setLevelFilter}>
                <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Toutes suspicions</SelectItem>
                  <SelectItem value="forte">Suspicion forte</SelectItem>
                  <SelectItem value="moyenne">Suspicion moyenne</SelectItem>
                  <SelectItem value="faible">Suspicion faible</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="overflow-x-auto max-h-[420px]">
              <table className="w-full text-sm" data-testid="detections-table">
                <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground sticky top-0">
                  <tr>
                    <th className="text-left px-3 py-2">Code</th>
                    <th className="text-left px-3 py-2">Score</th>
                    <th className="text-right px-3 py-2">Surface</th>
                    <th className="text-left px-3 py-2">Coordonnées</th>
                    <th className="text-right px-3 py-2">Cours d'eau</th>
                    <th className="text-left px-3 py-2">Statut</th>
                    <th className="text-left px-3 py-2">Suivi</th>
                  </tr>
                </thead>
                <tbody>
                  {detections.map((d) => (
                    <tr
                      key={d.id}
                      onClick={() => setSelected(d)}
                      className={`border-t border-border cursor-pointer hover:bg-muted/40 ${selected?.id === d.id ? "bg-primary/5" : ""}`}
                    >
                      <td className="px-3 py-2 font-mono font-semibold">{d.code}</td>
                      <td className="px-3 py-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${DETECTION_LEVEL_COLOR[d.level]}`}>{Math.round(d.score * 100)} %</span>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{d.area_ha} ha</td>
                      <td className="px-3 py-2 font-mono text-xs">{d.lat.toFixed(5)}, {d.lng.toFixed(5)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{d.indices.dist_water_m == null ? "—" : `${Math.round(d.indices.dist_water_m)} m`}</td>
                      <td className="px-3 py-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${DETECTION_STATUS_COLOR[d.status]}`}>{DETECTION_STATUS_LABEL[d.status]}</span>
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {[d.mission_id && "drone", d.alert_id && "alerte", d.known_site_id && "site connu"].filter(Boolean).join(" · ") || "—"}
                      </td>
                    </tr>
                  ))}
                  {!detections.length && (
                    <tr><td colSpan={7} className="px-3 py-10 text-center text-muted-foreground">
                      Aucune zone suspecte pour ces filtres. Lancez une analyse sur la zone sélectionnée.
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="runs">
          <Card className="border border-border shadow-none overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="text-left px-3 py-2">Lancée le</th>
                  <th className="text-left px-3 py-2">Référence</th>
                  <th className="text-left px-3 py-2">Récente</th>
                  <th className="text-left px-3 py-2">Source</th>
                  <th className="text-left px-3 py-2">Statut</th>
                  <th className="text-right px-3 py-2">Nouvelles zones</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id} className="border-t border-border align-top">
                    <td className="px-3 py-2">{fmtDateTime(r.started_at)}</td>
                    <td className="px-3 py-2 text-xs">{r.ref_start} → {r.ref_end}</td>
                    <td className="px-3 py-2 text-xs">{r.recent_start} → {r.recent_end}</td>
                    <td className="px-3 py-2 text-xs">
                      {r.mode === "simulation" ? <span className="text-amber-700 font-medium">Démonstration (fictif)</span> : `Sentinel-2 · ${r.images_used?.reference ?? "?"} + ${r.images_used?.recente ?? "?"} images`}
                    </td>
                    <td className="px-3 py-2">
                      {RUN_STATUS[r.status]}
                      {r.error && <div className="text-xs text-destructive max-w-xs">{r.error}</div>}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{r.status === "terminee" ? r.detections_count : "—"}</td>
                  </tr>
                ))}
                {!runs.length && <tr><td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">Aucune analyse sur cette zone.</td></tr>}
              </tbody>
            </table>
          </Card>
        </TabsContent>

        <TabsContent value="sites">
          <Card className="border border-border shadow-none">
            <div className="flex flex-wrap items-center justify-between gap-3 p-4 border-b border-border">
              <p className="text-sm text-muted-foreground max-w-2xl">
                Importez vos sites d'orpaillage déjà géoréférencés (CSV avec colonnes nom, latitude, longitude en degrés décimaux,
                ou GeoJSON de points). Une détection proche d'un site connu gagne en suspicion, et le taux de détection des sites connus
                permet d'évaluer la méthode.
              </p>
              {canAnalyse && (
                <>
                  <input ref={siteInput} type="file" accept=".csv,.geojson,.json" className="hidden" onChange={(e) => importSites(e.target.files?.[0])} />
                  <Button variant="outline" onClick={() => siteInput.current?.click()} data-testid="import-sites-btn">
                    <Upload className="w-4 h-4 mr-2" />Importer des sites
                  </Button>
                </>
              )}
            </div>
            <div className="overflow-x-auto max-h-[360px]">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground sticky top-0">
                  <tr><th className="text-left px-3 py-2">Nom</th><th className="text-left px-3 py-2">Localité</th><th className="text-left px-3 py-2">Coordonnées</th><th className="text-left px-3 py-2">Statut</th></tr>
                </thead>
                <tbody>
                  {sites.map((s) => (
                    <tr key={s.id} className="border-t border-border">
                      <td className="px-3 py-2 font-medium">{s.name}</td>
                      <td className="px-3 py-2">{s.locality || "—"}</td>
                      <td className="px-3 py-2 font-mono text-xs">{s.lat.toFixed(5)}, {s.lng.toFixed(5)}</td>
                      <td className="px-3 py-2">{s.status}</td>
                    </tr>
                  ))}
                  {!sites.length && <tr><td colSpan={4} className="px-3 py-8 text-center text-muted-foreground">Aucun site connu importé.</td></tr>}
                </tbody>
              </table>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="method">
          <Card className="p-6 border border-border shadow-none text-sm leading-relaxed space-y-3 max-w-3xl">
            <p><span className="font-semibold">1. Images.</span> Deux composites médians Sentinel-2 (10 m) sans nuages : une période de référence et une période récente. Comparer les mêmes mois d'une année sur l'autre limite les fausses alertes liées aux saisons.</p>
            <p><span className="font-semibold">2. Indices.</span> NDVI (végétation), BSI (sol nu), MNDWI (eau) et NDTI (turbidité de l'eau).</p>
            <p><span className="font-semibold">3. Pixels candidats.</span> Végétation dense auparavant, forte perte de NDVI, puis sol nu ou bassin d'eau turbide sur l'image récente. Le bâti (ESA WorldCover) et l'eau permanente (JRC) sont exclus.</p>
            <p><span className="font-semibold">4. Zones.</span> Les pixels voisins sont regroupés en polygones ; les zones plus petites que la surface minimale sont écartées.</p>
            <p><span className="font-semibold">5. Score.</span> Perte de végétation 35 %, sol nu 25 %, proximité d'un cours d'eau 20 %, turbidité 10 %, surface 10 %. Un site connu à proximité ajoute 10 points. Forte ≥ 70 %, moyenne ≥ 45 %.</p>
            <p><span className="font-semibold">6. Vérification.</span> Présumé (satellite) → précisé (drone) → confirmé ou infirmé (terrain). Les zones déjà détectées ne sont pas recréées lors des analyses suivantes.</p>
            <p className="text-muted-foreground">Limites : une zone suspecte n'est pas une preuve. Défrichements agricoles, carrières et chantiers peuvent produire le même signal ; seule la vérification terrain permet de conclure.</p>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Nouvelle zone */}
      <Dialog open={zoneOpen} onOpenChange={setZoneOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Nouvelle zone de surveillance</DialogTitle>
            <DialogDescription>Importez la limite en GeoJSON (export QGIS) ou saisissez une emprise rectangulaire en degrés décimaux.</DialogDescription>
          </DialogHeader>
          <form onSubmit={createZone} className="space-y-3">
            <div><Label>Nom</Label><Input required value={zoneForm.name} onChange={(e) => setZoneForm({ ...zoneForm, name: e.target.value })} placeholder="Zone de Seriyo" /></div>
            <div><Label>Description</Label><Textarea rows={2} value={zoneForm.description} onChange={(e) => setZoneForm({ ...zoneForm, description: e.target.value })} /></div>
            <div>
              <Label>Limite GeoJSON (facultatif)</Label>
              <Input type="file" accept=".geojson,.json" onChange={(e) => readZoneFile(e.target.files?.[0])} />
              {zoneGeo && <p className="text-xs text-emerald-700 mt-1">Limite chargée ({zoneGeo.type}). L'emprise ci-dessous sera ignorée.</p>}
            </div>
            {!zoneGeo && (
              <div className="grid grid-cols-2 gap-2">
                {[["min_lat", "Latitude min."], ["max_lat", "Latitude max."], ["min_lng", "Longitude min."], ["max_lng", "Longitude max."]].map(([k, l]) => (
                  <div key={k}><Label className="text-xs">{l}</Label><Input required inputMode="decimal" value={zoneForm[k]} onChange={(e) => setZoneForm({ ...zoneForm, [k]: e.target.value })} placeholder={k.includes("lat") ? "6.12" : "-5.95"} /></div>
                ))}
              </div>
            )}
            <DialogFooter><Button type="submit">Créer la zone</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Statut */}
      <Dialog open={statusOpen} onOpenChange={setStatusOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Statut de {selected?.code}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Select value={newStatus} onValueChange={setNewStatus}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{DETECTION_STATUS_LABEL[s]}</SelectItem>)}</SelectContent>
            </Select>
            <Textarea rows={3} value={statusNote} onChange={(e) => setStatusNote(e.target.value)} placeholder="Observation : nombre de puits, engins, produits, mission concernée…" />
          </div>
          <DialogFooter><Button onClick={saveStatus}>Enregistrer</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Mission drone */}
      <Dialog open={missionOpen} onOpenChange={setMissionOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mission drone sur {selected?.code}</DialogTitle>
            <DialogDescription>La mission apparaîtra dans « Missions drone », rattachée à la forêt classée la plus proche.</DialogDescription>
          </DialogHeader>
          <div><Label>Date prévue</Label><Input type="date" value={missionDate} onChange={(e) => setMissionDate(e.target.value)} /></div>
          <DialogFooter><Button onClick={createMission}><Plane className="w-4 h-4 mr-2" />Planifier</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
