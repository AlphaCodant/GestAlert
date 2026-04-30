import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Trees, Satellite, Plane, Eye, Sparkles, Brain, ArrowRight, ShieldCheck, MapPin,
} from "lucide-react";

const HERO_IMG =
  "https://images.unsplash.com/photo-1678188416081-a0135754c241?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODd8MHwxfHNlYXJjaHwxfHx0cm9waWNhbCUyMGZvcmVzdCUyMGFlcmlhbCUyMHZpZXd8ZW58MHx8fHwxNzc3NTkxNzUwfDA&ixlib=rb-4.1.0&q=85";
const DRONE_IMG =
  "https://images.unsplash.com/photo-1730470824798-9a50f3a7c752?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1ODF8MHwxfHNlYXJjaHwzfHxkcm9uZSUyMGZseWluZyUyMG92ZXIlMjBmb3Jlc3R8ZW58MHx8fHwxNzc3NTkxNzUwfDA&ixlib=rb-4.1.0&q=85";
const FIELD_IMG =
  "https://images.unsplash.com/photo-1764639564617-097064dc7097?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Nzd8MHwxfHNlYXJjaHwxfHxmb3Jlc3QlMjByYW5nZXIlMjB0cmFja2luZ3xlbnwwfHx8fDE3Nzc1OTE3NTB8MA&ixlib=rb-4.1.0&q=85";
const RIVER_IMG =
  "https://images.unsplash.com/photo-1770764171386-5bf604244678?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODd8MHwxfHNlYXJjaHwyfHx0cm9waWNhbCUyMGZvcmVzdCUyMGFlcmlhbCUyMHZpZXd8ZW58MHx8fHwxNzc3NTkxNzUwfDA&ixlib=rb-4.1.0&q=85";

export default function Landing() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-background/70 border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="landing-logo">
            <div className="w-9 h-9 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
              <Trees className="w-5 h-5" />
            </div>
            <div>
              <div className="font-display font-bold text-lg leading-none">GestPro</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mt-1">Gagnoa</div>
            </div>
          </Link>
          <nav className="hidden md:flex items-center gap-8 text-sm">
            <a href="#features" className="text-foreground/70 hover:text-foreground transition-colors">Fonctionnalités</a>
            <a href="#forests" className="text-foreground/70 hover:text-foreground transition-colors">Forêts</a>
            <a href="#tech" className="text-foreground/70 hover:text-foreground transition-colors">Technologies</a>
          </nav>
          <Link to="/login">
            <Button data-testid="header-login-btn">Connexion</Button>
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <img src={HERO_IMG} alt="Forêt tropicale" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-r from-background via-background/85 to-background/30" />
        </div>
        <div className="relative max-w-7xl mx-auto px-6 py-24 lg:py-32">
          <div className="max-w-2xl animate-fade-in">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-secondary text-secondary-foreground text-xs uppercase tracking-[0.18em] font-semibold">
              <ShieldCheck className="w-3.5 h-3.5" />
              Centre de Gestion de Gagnoa · Côte d'Ivoire
            </div>
            <h1 className="mt-6 font-display font-bold text-4xl sm:text-5xl lg:text-6xl tracking-tight leading-none text-foreground">
              Surveiller les forêts classées en <span className="text-primary">temps quasi-réel</span>.
            </h1>
            <p className="mt-6 text-base lg:text-lg text-foreground/75 leading-relaxed max-w-xl">
              GestPro combine imagerie satellitaire (Sentinel-2, Landsat, MODIS), intelligence artificielle,
              drones multispectraux et observations terrain pour détecter, vérifier et prévenir les
              activités illégales sur les Forêts Classées de Sangoué et de Téné.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/login">
                <Button size="lg" className="font-semibold" data-testid="hero-cta-btn">
                  Accéder à la plateforme
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
              <a href="#features">
                <Button size="lg" variant="outline" className="font-semibold">
                  Découvrir
                </Button>
              </a>
            </div>

            <div className="mt-10 grid grid-cols-3 gap-6 max-w-md">
              {[
                { v: "65 900", l: "ha surveillés" },
                { v: "5", l: "types d'alertes" },
                { v: "24/7", l: "détection" },
              ].map((s) => (
                <div key={s.l}>
                  <div className="text-2xl lg:text-3xl font-display font-bold text-primary">{s.v}</div>
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mt-1">{s.l}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 px-6 max-w-7xl mx-auto">
        <div className="max-w-2xl mb-12">
          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Modules</div>
          <h2 className="mt-3 font-display font-bold text-3xl lg:text-4xl tracking-tight">
            Une plateforme intégrée pour la surveillance forestière
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
          {[
            { i: Satellite, t: "Imagerie satellite (GEE)", d: "Analyse temporelle de Sentinel-2, Landsat & MODIS. Indices NDVI, NBR, NDWI calculés automatiquement.", c: "md:col-span-6" },
            { i: Brain, t: "IA & Détection d'anomalies", d: "Classification de couverture, détection de changements et plantations cacao via Random Forest et CNN.", c: "md:col-span-6" },
            { i: Plane, t: "Drones multispectraux", d: "Vérification haute résolution (3-5 cm/pixel) avec DJI Mavic 3 Multispectral.", c: "md:col-span-4" },
            { i: Eye, t: "Observations terrain", d: "Application mobile pour agents : géolocalisation, photos, formulaires hors-ligne.", c: "md:col-span-4" },
            { i: Sparkles, t: "Prédictions de risque", d: "Carte de probabilité de déforestation à 90 jours.", c: "md:col-span-4" },
          ].map((f, idx) => (
            <div
              key={idx}
              className={`${f.c} bg-card border border-border rounded-lg p-6 hover:-translate-y-1 hover:shadow-md transition-all`}
            >
              <div className="w-10 h-10 rounded-md bg-primary/10 text-primary flex items-center justify-center mb-4">
                <f.i className="w-5 h-5" />
              </div>
              <h3 className="font-display font-semibold text-lg mb-2">{f.t}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Forests focus */}
      <section id="forests" className="py-24 bg-secondary/40">
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Périmètre couvert</div>
            <h2 className="mt-3 font-display font-bold text-3xl lg:text-4xl tracking-tight">
              FC Sangoué & FC Téné
            </h2>
            <p className="mt-5 text-foreground/75 leading-relaxed">
              Deux forêts classées emblématiques du Centre de Gagnoa, totalisant <strong>65 900 ha</strong>,
              soumises à une forte pression agricole liée à la culture du cacao.
            </p>
            <div className="mt-8 grid grid-cols-2 gap-4">
              <div className="bg-card border border-border rounded-lg p-5">
                <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-[0.18em] font-semibold">
                  <MapPin className="w-3.5 h-3.5" />
                  Sangoué
                </div>
                <div className="mt-3 font-display text-3xl font-bold text-primary">36 200 <span className="text-base font-normal text-muted-foreground">ha</span></div>
              </div>
              <div className="bg-card border border-border rounded-lg p-5">
                <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-[0.18em] font-semibold">
                  <MapPin className="w-3.5 h-3.5" />
                  Téné
                </div>
                <div className="mt-3 font-display text-3xl font-bold text-primary">29 700 <span className="text-base font-normal text-muted-foreground">ha</span></div>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <img src={DRONE_IMG} alt="Drone" className="rounded-lg object-cover h-64 w-full col-span-2" />
            <img src={FIELD_IMG} alt="Agents terrain" className="rounded-lg object-cover h-44 w-full" />
            <img src={RIVER_IMG} alt="Forêt" className="rounded-lg object-cover h-44 w-full" />
          </div>
        </div>
      </section>

      {/* Tech stack */}
      <section id="tech" className="py-24 max-w-7xl mx-auto px-6">
        <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Technologies</div>
        <h2 className="mt-3 font-display font-bold text-3xl lg:text-4xl tracking-tight">Construit avec FastAPI & Google Earth Engine</h2>
        <div className="mt-10 flex flex-wrap gap-3">
          {["FastAPI", "MongoDB", "Google Earth Engine", "React", "Leaflet", "Claude Sonnet 4.5", "Sentinel-2", "Landsat-9", "MODIS", "DJI Mavic 3"].map((t) => (
            <span key={t} className="px-4 py-2 rounded-full bg-card border border-border text-sm font-medium">{t}</span>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-10 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <div className="font-display font-bold">GestPro</div>
            <div className="text-sm text-muted-foreground">Plateforme de surveillance des forêts classées · Centre de Gestion de Gagnoa</div>
          </div>
          <div className="text-xs text-muted-foreground uppercase tracking-[0.2em]">© 2026 · République de Côte d'Ivoire</div>
        </div>
      </footer>
    </div>
  );
}
