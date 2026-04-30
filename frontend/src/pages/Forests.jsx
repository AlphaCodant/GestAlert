import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Loader2, Trees, MapPin } from "lucide-react";
import ForestMap from "@/components/ForestMap";

export default function Forests() {
  const [forests, setForests] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/forests").then((r) => setForests(r.data)).finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="forests-page">
      <header>
        <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Périmètre</div>
        <h1 className="font-display font-bold text-3xl lg:text-4xl tracking-tight mt-1">Forêts classées</h1>
        <p className="text-sm text-muted-foreground mt-1">Centre de Gestion de Gagnoa</p>
      </header>

      {loading ? <Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" /> : (
        <>
          <Card className="p-4 border border-border shadow-none">
            <div style={{ height: 480 }}>
              <ForestMap forests={forests} fit />
            </div>
          </Card>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {forests.map((f) => (
              <Card key={f.id} className="p-6 border border-border shadow-none" data-testid={`forest-card-${f.id}`}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                    <Trees className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">{f.code}</div>
                    <h3 className="font-display font-bold text-xl">{f.name}</h3>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold">Superficie</div>
                    <div className="font-display text-2xl font-light text-primary mt-1">
                      {f.area_ha.toLocaleString("fr-FR")} <span className="text-base">ha</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold">Région</div>
                    <div className="text-sm mt-1 flex items-center gap-1"><MapPin className="w-3 h-3" />{f.region}</div>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground mt-4 leading-relaxed">{f.description}</p>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
