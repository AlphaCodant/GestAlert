import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Brain, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { fmtDateTime } from "@/lib/constants";

export default function AIAnalysis() {
  const [text, setText] = useState("");
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  async function loadHistory() {
    const r = await api.get("/ai/history");
    setHistory(r.data);
  }
  useEffect(() => { loadHistory(); }, []);

  async function analyze(e) {
    e.preventDefault();
    if (!text.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const r = await api.post("/ai/analyze", { text, context: context || null });
      setResult(r.data);
      loadHistory();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Erreur lors de l'analyse IA");
    } finally {
      setLoading(false);
    }
  }

  const examples = [
    "Plantation récente de cacao d'environ 5 ha détectée à l'intérieur de la forêt classée. Présence d'abris temporaires.",
    "Feu de brousse étendu sur la limite Sud de la forêt - environ 12 ha brûlés. Vent fort.",
    "Plusieurs arbres récemment coupés à proximité d'une piste illégale. Traces de tronçonneuse fraîches.",
  ];

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="ai-analysis-page">
      <header>
        <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Module IA</div>
        <h1 className="font-display font-bold text-3xl lg:text-4xl tracking-tight mt-1">Analyse intelligente</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Soumettez une observation à <span className="font-semibold text-primary">Claude Sonnet 4.5</span> pour obtenir analyse, gravité et recommandations.
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2 p-6 border border-border shadow-none">
          <form onSubmit={analyze} className="space-y-4">
            <div>
              <Label>Observation à analyser</Label>
              <Textarea
                rows={5}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Décrivez l'anomalie observée sur le terrain ou via satellite..."
                required
                data-testid="ai-text-input"
              />
            </div>
            <div>
              <Label>Contexte (optionnel)</Label>
              <Input
                value={context}
                onChange={(e) => setContext(e.target.value)}
                placeholder="Ex: FC Sangoué, secteur Nord, après alerte Sentinel-2"
                data-testid="ai-context-input"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {examples.map((ex, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setText(ex)}
                  className="text-xs px-3 py-1.5 rounded-full border border-border bg-muted/40 hover:border-primary"
                  data-testid={`ai-example-${i}`}
                >
                  Exemple {i + 1}
                </button>
              ))}
            </div>
            <Button type="submit" disabled={loading} data-testid="ai-analyze-btn">
              {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
              {loading ? "Analyse en cours..." : "Analyser avec Claude"}
            </Button>
          </form>

          {result && (
            <div className="mt-6 pt-6 border-t border-border" data-testid="ai-result">
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-primary font-semibold">
                <Brain className="w-3.5 h-3.5" />
                Analyse IA · {result.model}
              </div>
              <div className="mt-3 prose prose-sm max-w-none whitespace-pre-wrap text-foreground/90">
                {result.response}
              </div>
            </div>
          )}
        </Card>

        <Card className="p-5 border border-border shadow-none lg:max-h-[640px] overflow-auto">
          <h3 className="font-display font-semibold text-lg mb-3">Historique</h3>
          {history.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune analyse pour le moment</p>
          ) : (
            <div className="space-y-3">
              {history.map((h) => (
                <div key={h.id} className="border-l-2 border-primary/40 pl-3" data-testid={`ai-history-${h.id}`}>
                  <div className="text-xs text-muted-foreground">{fmtDateTime(h.created_at)}</div>
                  <div className="text-sm font-medium mt-1 line-clamp-2">{h.input_text}</div>
                  <button
                    onClick={() => setResult(h)}
                    className="text-xs text-primary hover:underline mt-1"
                  >Voir le résultat</button>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
