# GestPro — Plateforme de Surveillance des Forêts Classées de Gagnoa

## Problème original
> Crée moi cette application web nomée GestPro avec FastApi et GEE.

Application de surveillance intelligente des Forêts Classées du Centre de Gestion de Gagnoa (Côte d'Ivoire), combinant imagerie satellite (Sentinel-2, Landsat, MODIS via GEE), IA, drones multispectraux et observations terrain — désormais avec **PostgreSQL hébergé sur Render** + **intégration webhook Kobo Toolbox**.

## Choix utilisateur
- 1.b — Tous les modules (drones + prédictions IA inclus)
- 2.a — GEE simulé / mocké
- 3.a — Authentification JWT custom
- 4.b — Intégration LLM (Claude Sonnet 4.5) pour analyse textuelle
- 5 — Seed avec FC Sangoué (36 200 ha) + FC Téné (29 700 ha)
- **(Itération 2)** PostgreSQL externe Render + migration MongoDB→PG + Kobo webhook + mapping selon type formulaire

## Architecture
- **Backend** : FastAPI + SQLAlchemy 2.0 (async) + asyncpg + PostgreSQL 16 (Render Oregon, SSL)
- **Frontend** : React 19 + react-router-dom + react-leaflet + Recharts + shadcn/ui + Tailwind
- **IA** : Claude Sonnet 4.5 via emergentintegrations (clé universelle Emergent)
- **Cartes** : Leaflet + tuiles OSM / Esri Satellite / OpenTopoMap
- **Polices** : Outfit (titres) + Manrope (corps)
- **Intégration terrain** : Webhook Kobo Toolbox avec authentification par token (`X-Kobo-Token`)

## Personas / Rôles
- **Administrateur** — gestion globale, utilisateurs, configuration Kobo
- **Analyste SIG** — analyse satellite/drone, validation alertes
- **Agent terrain** — vérification d'alertes, observations terrain (manuel + Kobo)
- **Pilote drone** — planification & exécution missions drone

## Schéma PostgreSQL (tables)
- `users` (auth bcrypt + rôles)
- `forests` (FC Sangoué, FC Téné)
- `alerts` (avec `history` JSONB)
- `observations` (source `manuel` ou `kobo`, lien `kobo_submission_id`)
- `drone_missions`
- `ai_analyses` (historique Claude par utilisateur)
- `kobo_submissions` (raw payload JSONB + champs extraits)

## Intégration Kobo Toolbox
- **Endpoint** : `POST /api/kobo/webhook` (header `X-Kobo-Token` requis)
- **Configuration** : page `/dashboard/kobo` affiche l'URL HTTPS et le token à copier-coller dans Kobo → Settings → REST Services
- **Classification automatique** :
  - `verification` si `form_id` contient "verif" ou si `alert_id` présent
  - `infraction` si `form_id` contient "infract"
  - `observation` par défaut
- **Auto-mapping** :
  - Crée automatiquement une `Observation` (source=kobo) pour types `observation`/`verification` quand lat/lng disponibles
  - Pour `verification` avec `alert_id` valide, ajoute une entrée à l'historique de l'alerte (statut → `en_verification`)
  - Forêt résolue par `forest_id`/`code`/`name` ou par proximité géographique

## Fonctionnalités implémentées
### Backend (38/38 tests pytest ✓ - itération 4)
- Authentification JWT (cookie httpOnly + Bearer) avec 4 rôles
- Seed automatique : 4 utilisateurs démo + 2 forêts classées + ~14 alertes + ~9 observations + ~7 missions
- CRUD complet : alertes (workflow Détectée→Vérification→Confirmée→Résolue avec historique), observations terrain, missions drone (NDVI auto)
- GEE mock : indices NDVI/NBR/NDWI sur 12 mois + classification couverture des sols
- Prédictions déforestation : grille 8x8 cellules de risque
- Statistiques tableau de bord (incluant `kobo_submissions`)
- Analyse IA Claude Sonnet 4.5
- Gestion utilisateurs (admin only)
- **Webhook Kobo** avec extraction de champs flexible (`_geolocation`, `geopoint`, `lat`/`lng`, `description`, `_submitted_by`)
- Migration MongoDB → PostgreSQL via `migrate_mongo_to_pg.py`

### Frontend (12+ tests E2E ✓)
- Landing page + Login
- Dashboard SIG, Alertes, Observations, Missions drone, Prédictions, Indices GEE, Analyse IA, **Soumissions Kobo**, Forêts, Utilisateurs
- Page Kobo avec :
  - Card de configuration (URL webhook + token, copier en 1 clic)
  - Carte Leaflet des soumissions géolocalisées
  - Tableau des soumissions (type, agent, position, description, statut traité, date)
  - Visualiseur de payload brut JSON

## Backlog / Prochaines étapes
### P1 — Améliorations à court terme
- Intégration GEE réelle (compte de service Google + clé JSON)
- Notifications email/SMS sur alertes critiques
- Upload photos via Kobo (téléchargement automatique des `_attachments` Kobo dans object storage)
- Export PDF des rapports d'infraction (avec photos + analyse Claude)

### P2 — Évolutions
- Retry automatique côté Kobo en cas d'échec webhook (file de messages)
- Mapping personnalisable des champs Kobo via interface admin
- Modèle ML prédictif réel
- Notifications push aux agents quand une alerte les concerne

### P3 — Long terme
- Application mobile React Native offline-first pour zones sans réseau
- Pipeline ML d'orthomosaïque + DSM depuis les drones DJI
- Multi-tenant (autres centres de gestion)

## Identifiants de test
Voir `/app/memory/test_credentials.md`
- KOBO_WEBHOOK_SECRET = `gestpro_kobo_2026_secret_token`

## URL Preview
- App : https://geefastapi.preview.emergentagent.com
- Webhook Kobo : https://geefastapi.preview.emergentagent.com/api/kobo/webhook
