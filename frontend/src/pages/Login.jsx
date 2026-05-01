import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Trees, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";

const DEMO = [
  { role: "Administrateur", email: "admin@gestpro.ci", password: "GestPro2026!" },
  { role: "Analyste SIG", email: "analyste@gestpro.ci", password: "Analyste2026!" },
  { role: "Agent terrain", email: "agent@gestpro.ci", password: "Agent2026!" },
  { role: "Pilote drone", email: "pilote@gestpro.ci", password: "Pilote2026!" },
];

export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) navigate("/dashboard", { replace: true });
  }, [user, navigate]);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    const res = await login(email, password);
    setLoading(false);
    if (res.success) {
      toast.success("Connexion réussie");
      navigate("/dashboard");
    } else {
      toast.error(res.error || "Erreur de connexion");
    }
  }

  function fill(d) {
    setEmail(d.email);
    setPassword(d.password);
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      {/* Left visual */}
      <div className="hidden lg:flex relative overflow-hidden bg-primary">
        <img
          src="https://images.unsplash.com/photo-1678188416081-a0135754c241?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODd8MHwxfHNlYXJjaHwxfHx0cm9waWNhbCUyMGZvcmVzdCUyMGFlcmlhbCUyMHZpZXd8ZW58MHx8fHwxNzc3NTkxNzUwfDA&ixlib=rb-4.1.0&q=85"
          alt="Forêt"
          className="absolute inset-0 w-full h-full object-cover opacity-60"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-primary/80 via-primary/40 to-transparent" />
        <div className="relative z-10 flex flex-col justify-between p-12 text-primary-foreground">
          <Link to="/" className="flex items-center gap-2 group" data-testid="login-logo-link">
            <div className="w-10 h-10 rounded-lg bg-white text-primary flex items-center justify-center">
              <Trees className="w-5 h-5" />
            </div>
            <div>
              <div className="font-display font-bold text-xl leading-none">GestPro</div>
              <div className="text-[10px] uppercase tracking-[0.2em] mt-1 opacity-80">Gagnoa</div>
            </div>
          </Link>
          <div>
            <div className="text-xs uppercase tracking-[0.25em] opacity-70 mb-3">Plateforme de surveillance</div>
            <h2 className="font-display font-bold text-3xl lg:text-4xl leading-tight">
              Protéger les forêts classées de Côte d'Ivoire grâce aux données satellites & à l'IA.
            </h2>
            <p className="mt-4 text-sm opacity-80 max-w-md">
              FC Sangoué (36 200 ha) · FC Téné (29 700 ha)
            </p>
          </div>
        </div>
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-8">
            <Link to="/" className="flex items-center gap-2" data-testid="login-mobile-logo">
              <div className="w-9 h-9 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
                <Trees className="w-5 h-5" />
              </div>
              <div className="font-display font-bold text-lg">GestPro</div>
            </Link>
          </div>

          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Connexion</div>
          <h1 className="mt-2 font-display font-bold text-3xl lg:text-4xl tracking-tight">
            Bienvenue sur GestPro
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            Accédez à votre espace de surveillance.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4" data-testid="login-form">
            <div>
              <Label htmlFor="email">Adresse email</Label>
              <Input
                id="email" type="email" required
                value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="vous@gestpro.ci"
                data-testid="login-email-input"
                className="mt-1.5"
              />
            </div>
            <div>
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password" type="password" required
                value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                data-testid="login-password-input"
                className="mt-1.5"
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading} data-testid="login-submit-btn">
              {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              {loading ? "Connexion..." : "Se connecter"}
            </Button>
          </form>

          <div className="mt-8 pt-6 border-t border-border">
            <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold mb-3">
              Comptes de démonstration
            </div>
            <div className="grid grid-cols-2 gap-2">
              {DEMO.map((d) => (
                <button
                  key={d.email}
                  type="button"
                  onClick={() => fill(d)}
                  data-testid={`demo-login-${d.role.toLowerCase().replace(/ /g, "-")}`}
                  className="text-left text-xs px-3 py-2 rounded-md border border-border bg-card hover:border-primary hover:bg-primary/5 transition"
                >
                  <div className="font-semibold">{d.role}</div>
                  <div className="text-muted-foreground truncate">{d.email}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <Toaster richColors position="top-right" />
    </div>
  );
}
