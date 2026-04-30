import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Plus, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { ROLE_LABEL, fmtDateTime } from "@/lib/constants";
import { useAuth } from "@/contexts/AuthContext";

const ROLES = ["admin", "analyste_sig", "agent_terrain", "pilote_drone"];

export default function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", full_name: "", role: "agent_terrain" });

  async function load() {
    setLoading(true);
    try { const r = await api.get("/users"); setUsers(r.data); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function submit(e) {
    e.preventDefault();
    try {
      await api.post("/auth/register", form);
      toast.success("Utilisateur créé");
      setOpen(false);
      setForm({ email: "", password: "", full_name: "", role: "agent_terrain" });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Erreur"); }
  }

  async function del(id) {
    if (!confirm("Supprimer cet utilisateur ?")) return;
    try {
      await api.delete(`/users/${id}`);
      toast.success("Utilisateur supprimé");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Erreur"); }
  }

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="users-page">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-semibold">Administration</div>
          <h1 className="font-display font-bold text-3xl lg:text-4xl tracking-tight mt-1">Utilisateurs</h1>
          <p className="text-sm text-muted-foreground mt-1">Gestion des comptes et rôles</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button data-testid="create-user-btn"><Plus className="w-4 h-4 mr-2" />Nouvel utilisateur</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Créer un utilisateur</DialogTitle></DialogHeader>
            <form onSubmit={submit} className="space-y-3">
              <div><Label>Nom complet</Label><Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required data-testid="user-name-input" /></div>
              <div><Label>Email</Label><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required data-testid="user-email-input" /></div>
              <div><Label>Mot de passe</Label><Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={6} data-testid="user-password-input" /></div>
              <div>
                <Label>Rôle</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger data-testid="user-role-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{ROLES.map((r) => <SelectItem key={r} value={r}>{ROLE_LABEL[r]}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <DialogFooter><Button type="submit" data-testid="user-submit-btn">Créer</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </header>

      <Card className="border border-border shadow-none overflow-hidden">
        {loading ? <div className="p-12 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div> : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="text-left p-3 font-semibold">Nom</th>
                <th className="text-left p-3 font-semibold">Email</th>
                <th className="text-left p-3 font-semibold">Rôle</th>
                <th className="text-left p-3 font-semibold">Créé le</th>
                <th className="text-right p-3 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-border hover:bg-muted/20" data-testid={`user-row-${u.id}`}>
                  <td className="p-3 font-medium">{u.full_name}</td>
                  <td className="p-3 text-muted-foreground">{u.email}</td>
                  <td className="p-3">
                    <span className="text-xs px-2 py-0.5 rounded border bg-secondary/50">{ROLE_LABEL[u.role] || u.role}</span>
                  </td>
                  <td className="p-3 text-xs text-muted-foreground">{fmtDateTime(u.created_at)}</td>
                  <td className="p-3 text-right">
                    {u.id !== me?.id && (
                      <Button size="sm" variant="ghost" onClick={() => del(u.id)} data-testid={`delete-user-${u.id}`}>
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
