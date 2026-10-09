# GestPro : surveillance des forêts classées et lutte contre l'orpaillage (Gagnoa, Région du Gôh)

GestPro est une plateforme web de surveillance. Elle combine les éléments suivants :

- l'imagerie satellite ;
- les missions drone ;
- les observations terrain, notamment via Kobo Toolbox ;
- l'analyse par IA.

Pile technique : FastAPI, PostgreSQL et React.

- **Module Orpaillage** : détection satellitaire (Sentinel-2 via Google Earth Engine) des zones susceptibles d'être des sites d'orpaillage illégal, puis leur vérification par drone et sur le terrain. Voir [docs/ORPAILLAGE.md](docs/ORPAILLAGE.md).
- Spécifications générales : [memory/PRD.md](memory/PRD.md).
