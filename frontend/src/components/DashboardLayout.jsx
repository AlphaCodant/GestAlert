import React from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { ROLE_LABEL } from "@/lib/constants";
import ErrorBoundary from "@/components/ErrorBoundary";
import {
  LayoutDashboard, MapPin, Bell, Eye, Plane, Sparkles, Trees, Brain, Users, LogOut, Trees as Logo
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Toaster } from "@/components/ui/sonner";

const NAV = [
  { to: "/dashboard", label: "Tableau de bord", icon: LayoutDashboard, roles: null },
  { to: "/dashboard/alerts", label: "Alertes", icon: Bell, roles: null },
  { to: "/dashboard/observations", label: "Observations", icon: Eye, roles: null },
  { to: "/dashboard/drones", label: "Missions drone", icon: Plane, roles: null },
  { to: "/dashboard/predictions", label: "Prédictions", icon: Sparkles, roles: null },
  { to: "/dashboard/gee", label: "Indices GEE", icon: MapPin, roles: null },
  { to: "/dashboard/ai", label: "Analyse IA", icon: Brain, roles: null },
  { to: "/dashboard/forests", label: "Forêts classées", icon: Trees, roles: null },
  { to: "/dashboard/users", label: "Utilisateurs", icon: Users, roles: ["admin"] },
];

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  const allowed = (item) =>
    !item.roles || item.roles.includes(user?.role) || user?.role === "admin";

  return (
    <div className="min-h-screen flex bg-background gestpro-grain">
      {/* Sidebar */}
      <aside
        className="w-64 bg-card border-r border-border flex flex-col sticky top-0 h-screen"
        data-testid="sidebar"
      >
        <div className="px-6 py-5 border-b border-border">
          <NavLink to="/dashboard" className="flex items-center gap-2 group" data-testid="logo-link">
            <div className="w-9 h-9 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
              <Logo className="w-5 h-5" />
            </div>
            <div>
              <div className="font-display font-bold text-lg leading-none">GestPro</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mt-1">Gagnoa</div>
            </div>
          </NavLink>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {NAV.filter(allowed).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/dashboard"}
              data-testid={`nav-${item.to.replace(/\//g, "-").replace(/^-/, "")}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-foreground/70 hover:bg-muted hover:text-foreground"
                }`
              }
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-border p-3">
          <div className="px-2 py-2 rounded-md bg-muted/50">
            <div className="text-sm font-semibold truncate" data-testid="user-name">{user?.full_name}</div>
            <div className="text-xs text-muted-foreground truncate">{ROLE_LABEL[user?.role] || user?.role}</div>
          </div>
          <Button
            variant="ghost"
            className="w-full justify-start mt-2 text-foreground/70"
            onClick={handleLogout}
            data-testid="logout-btn"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Déconnexion
          </Button>
        </div>
      </aside>

      <main className="flex-1 min-w-0">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>

      <Toaster richColors position="top-right" />
    </div>
  );
}
