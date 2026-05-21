// GestPro - JS partagé
window.api = {
  async get(path) {
    const r = await fetch('/api' + path, { credentials: 'include' });
    if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch('/api' + path, {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
    return r.json();
  },
  async patch(path, body) {
    const r = await fetch('/api' + path, {
      method: 'PATCH', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
    return r.json();
  },
  async del(path) {
    const r = await fetch('/api' + path, { method: 'DELETE', credentials: 'include' });
    if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
    return r.json();
  },
};

window.fmtDateTime = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
};

window.LABELS = {
  type: {
    deforestation: 'Déforestation', agriculture_illegale: 'Agriculture illégale',
    feu_de_brousse: 'Feu de brousse', exploitation_illegale: 'Exploitation illégale',
    defrichement: 'Défrichement', autre: 'Autre',
  },
  status: {
    detectee: 'Détectée', en_verification: 'En vérification',
    confirmee: 'Confirmée', resolue: 'Résolue', rejetee: 'Rejetée',
  },
  severity: { faible: 'Faible', moyenne: 'Moyenne', haute: 'Haute', critique: 'Critique' },
  mission: { planifiee: 'Planifiée', en_cours: 'En cours', terminee: 'Terminée', annulee: 'Annulée' },
};

window.openModal = (id) => document.getElementById(id)?.classList.add('open');
window.closeModal = (id) => document.getElementById(id)?.classList.remove('open');

window.toast = (msg, type='success') => {
  const el = document.createElement('div');
  el.style.cssText = `position:fixed;bottom:1rem;right:1rem;padding:.75rem 1.25rem;border-radius:6px;color:white;font-weight:600;z-index:300;background:${type==='error'?'#dc2626':'#16a34a'};`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
};
