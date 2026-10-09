# Module Orpaillage : détection satellitaire dans la Région du Gôh

Le module repère dans les images Sentinel-2 les zones **susceptibles** d'être des sites d'orpaillage illégal. Il suit ensuite leur vérification jusqu'au terrain.

Page : **Tableau de bord → Orpaillage (satellite)** (`/dashboard/orpaillage`).

## Ce que fait le module

1. **Zones de surveillance.** Une zone « Région du Gôh » est créée au démarrage. Il s'agit d'une emprise rectangulaire **approximative** de Gagnoa et Oumé. Ajoutez vos propres zones (par exemple la zone de Seriyo) de deux façons :
   - en important un GeoJSON exporté de QGIS ;
   - en saisissant une emprise en degrés décimaux.
2. **Analyse.** L'analyse compare une période de référence et une période récente. Par défaut, elle prend les 120 derniers jours et la même fenêtre un an plus tôt.
3. **Zones suspectes.** Ce sont des polygones notés de 0 à 100 % selon le niveau de suspicion :
   - **forte** : 70 % ou plus ;
   - **moyenne** : 45 % ou plus ;
   - **faible** : en dessous de 45 %.
4. **Suivi.** Chaque zone passe par les statuts suivants :
   - **présumé** (satellite) ;
   - **précisé** (drone) ;
   - **confirmé** ou **infirmé** (terrain).

   L'historique de chaque changement est conservé. Depuis une zone, on peut créer une **alerte** (type « Orpaillage illégal ») ou une **mission drone**. Toutes deux sont rattachées à la forêt classée la plus proche.
5. **Sites connus.** Importez vos sites déjà géoréférencés en CSV ou GeoJSON. Une détection située près d'un site connu gagne 10 points de score.
6. **Exports.** Quatre formats sont disponibles :
   - **GPX** pour les GPS Garmin ;
   - **KML** pour Google Earth ;
   - **GeoJSON** pour QGIS ;
   - **CSV** pour Excel, avec point-virgule comme séparateur.

## Méthode de détection (Google Earth Engine)

| Étape | Détail |
| --- | --- |
| Images | Composites médians Sentinel-2 SR (`COPERNICUS/S2_SR_HARMONIZED`). Nuages, ombres et cirrus masqués avec la bande SCL. |
| Indices | NDVI (végétation), BSI (sol nu), MNDWI (eau), NDTI (turbidité). |
| Pixels candidats | NDVI de référence ≥ 0,4 **et** perte de NDVI ≥ seuil **et** (sol nu **ou** bassin d'eau turbide), hors bâti (ESA WorldCover classe 50) et hors eau permanente (JRC, occurrence ≥ 80 %). |
| Zones | Pixels contigus regroupés en polygones, à 10 m de résolution en UTM 30N. Les zones sous la surface minimale (0,5 ha par défaut) sont écartées. |
| Score | Perte de végétation 35 %, sol nu 25 %, proximité d'un cours d'eau 20 %, turbidité 10 %, surface 10 %, plus 10 points si un site connu est proche. |
| Doublons | Une zone déjà détectée sur la même emprise n'est pas recréée. Son historique note qu'elle est toujours visible. |

Tous les seuils se règlent dans l'interface, au moment de lancer l'analyse.

**Limites.** Une zone suspecte ne prouve rien. Un défrichement agricole, une carrière ou un chantier peut produire le même signal. Seule la vérification terrain permet de conclure. Le suivi du taux de confirmation permet d'ajuster les seuils.

## Configuration de Google Earth Engine

Sans configuration, le module fonctionne en **mode démonstration**. Les zones affichées sont alors **fictives**, et un bandeau orange le signale sur la page.

Il faut une clé de **compte de service** Google au format JSON, et ce compte doit avoir accès à Earth Engine. Le projet Google Cloud doit être enregistré pour Earth Engine, et le compte doit avoir le rôle « Earth Engine Resource Viewer » ou « Service Usage Consumer ».

**Sur un poste ou un serveur** : placez le fichier JSON **hors du dépôt**, par exemple `C:\cles\gee.json`, puis ajoutez dans `backend/.env` :

```env
GEE_PRIVATE_KEY_FILE=C:\cles\gee.json
```

**Sur un hébergeur sans fichier (Render, Emergent)** : créez la variable d'environnement `GEE_SERVICE_ACCOUNT_JSON` et collez-y le contenu complet du fichier JSON.

`GEE_PROJECT` est facultatif : à défaut, le `project_id` de la clé est utilisé.

**Vérification** : depuis le dossier `backend`, lancez la commande suivante. Le bouton « Tester » de la page Orpaillage fait la même vérification.

```bash
python scripts/verifier_gee.py C:\cles\gee.json
```

**Sécurité.** Ne versionnez jamais la clé : `.gitignore` exclut déjà `.env`, `*.key` et `credentials.json`. Une clé qui a circulé dans un message ou un e-mail doit être remplacée. Dans Google Cloud, allez dans IAM, puis Comptes de service, puis Clés : créez une nouvelle clé et supprimez l'ancienne.

**Conseil.** Lancez les analyses sur des zones de quelques centaines de km², comme Seriyo, plutôt que sur toute la région. Elles sont plus rapides et restent sous les quotas de Google Earth Engine.

## Format d'import des sites connus

CSV séparé par `;` ou `,`, avec la virgule ou le point comme séparateur décimal. Coordonnées en degrés décimaux WGS84.

```csv
nom;latitude;longitude;localite;statut
Site 1;6,1234;-5,9876;Seriyo;actif
```

Les noms de colonnes reconnus sont les suivants :

| Information | Noms acceptés |
| --- | --- |
| Latitude | `lat`, `latitude`, `y` |
| Longitude | `lng`, `lon`, `longitude`, `x` |
| Nom | `nom`, `name`, `site`, `code` |
| Localité | `localite`, `village`, `foret`, `zone` |
| Statut | `statut`, `status`, `etat` |

Le GeoJSON doit contenir des entités de type Point.

## API

Toutes les routes commencent par `/api/orpaillage` et demandent une connexion. Créer une zone, lancer une analyse et importer des sites sont réservés aux rôles admin et analyste SIG.

| Méthode | Route | Rôle |
| --- | --- | --- |
| GET | `/config` | Mode (GEE ou démonstration), compte GEE utilisé, seuils par défaut |
| GET | `/gee-check` | Teste la connexion à Earth Engine |
| GET, POST, DELETE | `/zones` | Zones de surveillance |
| POST | `/runs` | Lancer une analyse (traitée en arrière-plan) |
| GET | `/runs`, `/runs/{id}` | Suivi des analyses |
| GET | `/detections` | Zones suspectes, filtrables par zone, analyse, statut, niveau et score |
| PATCH | `/detections/{id}/status` | Changer le statut avec une note |
| POST | `/detections/{id}/alert` | Créer une alerte |
| POST | `/detections/{id}/drone-mission` | Planifier une mission drone |
| GET | `/export?format=gpx\|kml\|geojson\|csv` | Exporter les zones |
| GET | `/known-sites` | Lister les sites connus |
| POST | `/known-sites/import` | Importer des sites connus |
| GET | `/stats` | Indicateurs |

## Tests

```bash
cd backend
python -m pytest tests/test_orpaillage.py                                      # tests unitaires
ORPAILLAGE_API_URL=http://localhost:8001 python -m pytest tests/test_orpaillage.py  # + parcours complet de l'API
```

Pour une base PostgreSQL locale sans SSL, ajoutez `DB_SSL=false` dans `backend/.env`.
