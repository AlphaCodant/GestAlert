# GestPro — Plateforme de Surveillance des Forêts Classées de Gagnoa

## Problème original
> Crée moi cette application web nomée GestPro avec FastApi et GEE.

Application de surveillance intelligente des Forêts Classées du Centre de Gestion de Gagnoa (Côte d'Ivoire), combinant imagerie satellite (Sentinel-2, Landsat, MODIS via GEE), IA, drones multispectraux et observations terrain.

## Choix utilisateur
- 1.b — Tous les modules (drones + prédictions IA inclus)
- 2.a — GEE simulé / mocké
- 3.a — Authentification JWT custom
- 4.b — Intégration LLM (Claude Sonnet 4.5) pour analyse textuelle
- 5 — Seed avec FC Sangoué (36 200 ha) + FC Téné (29 700 ha)

## Architecture
- **Backend** : FastAPI + Motor (MongoDB async) + JWT (PyJWT) + bcrypt
- **Frontend** : React 19 + react-router-dom + react-leaflet + Recharts + shadcn/ui + Tailwind
- **IA** : Claude Sonnet 4.5 via emergentintegrations (clé universelle Emergent)
- **Cartes** : Leaflet + tuiles OSM / Esri Satellite / OpenTopoMap
- **Polices** : Outfit (titres) + Manrope (corps) — Google Fonts

## Personas / Rôles
- **Administrateur** — gestion globale, utilisateurs, configuration
- **Analyste SIG** — analyse satellite/drone, validation alertes
- **Agent terrain** — vérification d'alertes, observations terrain
- **Pilote drone** — planification & exécution missions drone

## Fonctionnalités implémentées (30/04/2026)
### Backend (28/28 tests pytest ✓)
- Authentification JWT (cookie httpOnly + Bearer) avec 4 rôles
- Seed automatique : 4 utilisateurs démo + 2 forêts classées + ~14 alertes + ~9 observations + ~7 missions
- CRUD complet : alertes (workflow Détectée→Vérification→Confirmée→Résolue avec historique), observations terrain (avec géolocalisation), missions drone (planification, statuts, NDVI auto)
- GEE mock : indices NDVI/NBR/NDWI sur 12 mois + classification couverture des sols
- Prédictions déforestation : grille 8x8 cellules de risque (horizon 90j)
- Statistiques tableau de bord : KPIs, répartitions, alertes récentes
- Analyse IA Claude Sonnet 4.5 : structurée FR (analyse, gravité, causes, recommandations, priorité)
- Gestion utilisateurs (admin only)

### Frontend (12/12 tests E2E ✓)
- Landing page avec hero + sections fonctionnalités/forêts/tech
- Login (4 boutons quick-fill démo)
- Dashboard SIG avec KPIs, carte Leaflet interactive, alertes récentes, répartitions par type
- Module Alertes (tableau + filtres + création + workflow statuts avec historique)
- Module Observations (cartes + création + géolocalisation navigateur)
- Module Missions drone (cartes + création + suivi statuts)
- Module Prédictions (carte risque + zones critiques)
- Module Indices GEE (LineChart NDVI/NBR/NDWI + PieChart landcover)
- Module Analyse IA (formulaire Claude + historique)
- Module Forêts classées
- Module Utilisateurs (admin only) avec création/suppression
- RBAC : navigation conditionnelle, redirection auto pour rôles non autorisés
- ErrorBoundary global pour résilience

## Backlog / Prochaines étapes
### P1 — Améliorations à court terme
- Intégration GEE réelle (compte de service Google + clé JSON) au lieu de mock
- Application mobile React Native pour agents terrain (offline-first, photo)
- Notifications email/SMS sur alertes critiques (Resend/Twilio)
- Upload photos pour observations (object storage)
- Export PDF des rapports d'alerte/observation

### P2 — Évolutions
- Modèle IA prédictif réel (Random Forest sur données historiques)
- Détection automatique d'anomalies via classification supervisée Sentinel-2
- Calcul automatique d'indices via pipeline GEE en arrière-plan
- Tableau de bord administrateur étendu (audit trail, exports)
- Multi-tenant pour autres centres de gestion (Abengourou, Soubré, etc.)

### P3 — Long terme
- Intégration drones DJI réelle (téléchargement & traitement images multispectrales)
- Pipeline ML d'orthomosaïque + DSM
- Application web installable (PWA)

## Dépendances clés
- Backend : fastapi, motor, pyjwt, bcrypt, emergentintegrations, python-dotenv
- Frontend : react, react-router-dom, react-leaflet, leaflet, recharts, sonner, lucide-react, shadcn/ui

## Identifiants de test
Voir `/app/memory/test_credentials.md`

## URL Preview
https://geefastapi.preview.emergentagent.com
