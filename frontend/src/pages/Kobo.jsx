import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, ClipboardCopy, ExternalLink, Database, FileText, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { fmtDateTime } from "@/lib/constants";
import ForestMap from "@/components/ForestMap";

const FORM_TYPE_LABEL = {
  observation: "Observation terrain",
  verification: "Vérification d'alerte",
  infraction: "Infraction",
};

const FORM_TYPE_COLOR = {
  observation: "bg-emerald-100 text-emerald-800 border-emerald-300",
  verification: "bg-amber-100 text-amber-800 border-amber-300",
  infraction: "bg-red-100 text-red-800 border-red-300",
};

export default function Kobo() {
  const [submissions, setSubmissions] = useState([]);
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const [s, i] = await Promise.all([
        api.get("/kobo/submissions"),
        api.get("/kobo/info"),
      ]);
      setSubmissions(s.data);
      setInfo(i.data);
    } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  function copy(text) {
    navigator.clipboard.writeText(text);
    toast.success("Copié dans le presse-papier");
  }

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="kobo-page">
      <header>
        <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Intégration</div>
        <h1 className="font-display font-bold text-3xl lg:text-4xl tracking-tight mt-1">Soumissions Kobo Toolbox</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Centralisation des formulaires de vérification terrain envoyés depuis Kobo
        </p>
      </header>

      {/* Webhook config */}
      {info && (
        <Card className="p-6 border border-border shadow-none bg-secondary/40" data-testid="kobo-config-card">
          <div className="flex items-center gap-2 mb-3">
            <Database className="w-4 h-4 text-primary" />
            <h3 className="font-display font-semibold text-lg">Configuration du webhook</h3>
          </div>

          <div className="space-y-3 text-sm">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold mb-1">Endpoint URL</div>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-card border border-border rounded px-3 py-2 font-mono text-xs break-all" data-testid="webhook-url">
                  {info.webhook_url}
                </code>
                <Button size="sm" variant="outline" onClick={() => copy(info.webhook_url)} data-testid="copy-url-btn">
                  <ClipboardCopy className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>

            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold mb-1">
                Custom HTTP Header — {info.header_name}
              </div>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-card border border-border rounded px-3 py-2 font-mono text-xs break-all" data-testid="webhook-token">
                  {info.header_value}
                </code>
                <Button size="sm" variant="outline" onClick={() => copy(info.header_value)} data-testid="copy-token-btn">
                  <ClipboardCopy className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>

            <div className="pt-3 border-t border-border">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold mb-2">Étapes de configuration</div>
              <ol className="space-y-1.5 text-sm leading-relaxed list-decimal list-inside">
                {info.instructions.map((line, i) => (
                  <li key={i} className="text-foreground/80">{line.replace(/^\d+\.\s*/, "")}</li>
                ))}
              </ol>
              <a
                href="https://kf.kobotoolbox.org"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 mt-3 text-primary text-xs hover:underline"
                data-testid="kobo-external-link"
              >
                Ouvrir Kobo Toolbox <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </Card>
      )}

      {/* Map of submissions */}
      <Card className="p-4 border border-border shadow-none">
        <h3 className="font-display font-semibold text-base mb-3">Localisations des soumissions</h3>
        <div style={{ height: 360 }}>
          <ForestMap
            observations={submissions.filter((s) => s.lat != null && s.lng != null).map((s) => ({
              id: s.id, lat: s.lat, lng: s.lng,
              observation_type: s.form_type,
              description: s.description || "Soumission Kobo",
              agent_name: s.submitted_by || "Kobo",
            }))}
            fit={submissions.length > 0}
          />
        </div>
      </Card>

      {/* Submissions list */}
      <Card className="border border-border shadow-none overflow-hidden">
        {loading ? (
          <div className="p-12 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
        ) : submissions.length === 0 ? (
          <div className="p-12 text-center">
            <FileText className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">
              Aucune soumission Kobo reçue pour le moment.
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Configurez le webhook ci-dessus puis envoyez un formulaire depuis Kobo Toolbox.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="text-left p-3 font-semibold">Type</th>
                <th className="text-left p-3 font-semibold">Soumis par</th>
                <th className="text-left p-3 font-semibold">Position</th>
                <th className="text-left p-3 font-semibold">Description</th>
                <th className="text-left p-3 font-semibold">Statut</th>
                <th className="text-left p-3 font-semibold">Reçu le</th>
                <th className="text-right p-3 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {submissions.map((s) => (
                <tr key={s.id} className="border-b border-border hover:bg-muted/20" data-testid={`kobo-row-${s.id}`}>
                  <td className="p-3">
                    <span className={`text-xs px-2 py-0.5 rounded border ${FORM_TYPE_COLOR[s.form_type] || ""}`}>
                      {FORM_TYPE_LABEL[s.form_type] || s.form_type}
                    </span>
                  </td>
                  <td className="p-3 font-medium">{s.submitted_by || "—"}</td>
                  <td className="p-3 font-mono text-xs">
                    {s.lat != null ? `${s.lat.toFixed(4)}, ${s.lng.toFixed(4)}` : "—"}
                  </td>
                  <td className="p-3 text-xs max-w-xs truncate" title={s.description}>{s.description || "—"}</td>
                  <td className="p-3">
                    {s.processed ? (
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
                        <CheckCircle2 className="w-3 h-3" />Traité
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">En attente</span>
                    )}
                  </td>
                  <td className="p-3 text-xs text-muted-foreground">{fmtDateTime(s.received_at)}</td>
                  <td className="p-3 text-right">
                    <Button size="sm" variant="ghost" onClick={() => setSelected(s)} data-testid={`view-kobo-${s.id}`}>
                      Voir payload
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Payload viewer */}
      {selected && (
        <Card className="p-5 border border-border shadow-none" data-testid="kobo-payload-viewer">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display font-semibold text-base">Payload brut Kobo</h3>
            <Button size="sm" variant="ghost" onClick={() => setSelected(null)}>Fermer</Button>
          </div>
          <pre className="bg-muted/40 rounded p-4 text-xs overflow-auto max-h-96 font-mono">
            {JSON.stringify(selected.raw_payload, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  );
}
