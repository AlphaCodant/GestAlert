export const ROLE_LABEL = {
  admin: "Administrateur",
  analyste_sig: "Analyste SIG",
  agent_terrain: "Agent terrain",
  pilote_drone: "Pilote drone",
};

export const ALERT_TYPE_LABEL = {
  deforestation: "Déforestation",
  agriculture_illegale: "Agriculture illégale",
  feu_de_brousse: "Feu de brousse",
  exploitation_illegale: "Exploitation illégale",
  defrichement: "Défrichement",
  autre: "Autre",
};

export const ALERT_STATUS_LABEL = {
  detectee: "Détectée",
  en_verification: "En vérification",
  confirmee: "Confirmée",
  resolue: "Résolue",
  rejetee: "Rejetée",
};

export const SEVERITY_LABEL = {
  faible: "Faible",
  moyenne: "Moyenne",
  haute: "Haute",
  critique: "Critique",
};

export const SEVERITY_COLOR = {
  faible: "bg-emerald-100 text-emerald-800 border-emerald-300",
  moyenne: "bg-amber-100 text-amber-800 border-amber-300",
  haute: "bg-orange-100 text-orange-800 border-orange-300",
  critique: "bg-red-100 text-red-800 border-red-300",
};

export const STATUS_COLOR = {
  detectee: "bg-blue-100 text-blue-800 border-blue-300",
  en_verification: "bg-yellow-100 text-yellow-800 border-yellow-300",
  confirmee: "bg-orange-100 text-orange-800 border-orange-300",
  resolue: "bg-emerald-100 text-emerald-800 border-emerald-300",
  rejetee: "bg-zinc-100 text-zinc-700 border-zinc-300",
};

export const MISSION_STATUS_LABEL = {
  planifiee: "Planifiée",
  en_cours: "En cours",
  terminee: "Terminée",
  annulee: "Annulée",
};

export const MISSION_STATUS_COLOR = {
  planifiee: "bg-blue-100 text-blue-800 border-blue-300",
  en_cours: "bg-amber-100 text-amber-800 border-amber-300",
  terminee: "bg-emerald-100 text-emerald-800 border-emerald-300",
  annulee: "bg-zinc-100 text-zinc-700 border-zinc-300",
};

export function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit", month: "short", year: "numeric",
    });
  } catch { return iso; }
}

export function fmtDateTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fr-FR", {
      day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}
