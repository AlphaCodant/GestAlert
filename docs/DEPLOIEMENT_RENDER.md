# Déployer GestPro sur Render

L'application se compose de trois éléments sur Render :

| Élément | Type Render | Rôle |
| --- | --- | --- |
| Base de données | PostgreSQL (déjà existante, région Oregon) | Données |
| `gestpro-api` | Web Service (Python) | API FastAPI, analyses GEE |
| `gestpro` | Static Site | Interface React |

Le fichier `render.yaml`, à la racine du dépôt, décrit les deux services.

## 1. Préparer les valeurs

| Variable | Où la trouver |
| --- | --- |
| `DATABASE_URL` | Base Render → Connections → **Internal Database URL**. Le préfixe `postgresql://` est accepté tel quel. |
| `ADMIN_PASSWORD` | À choisir. C'est le mot de passe du compte `admin@gestpro.ci`. |
| `GEE_SERVICE_ACCOUNT_JSON` | Contenu **complet** de la nouvelle clé JSON du compte de service, de `{` à `}`. |
| `CORS_ORIGINS` | Adresse du frontend, par exemple `https://gestpro.onrender.com`. |
| `REACT_APP_BACKEND_URL` | Adresse de l'API, par exemple `https://gestpro-api.onrender.com`. |
| `PUBLIC_BASE_URL` | Même valeur que `REACT_APP_BACKEND_URL`. Sert à afficher l'URL du webhook Kobo. |
| `KOBO_WEBHOOK_SECRET` | Facultatif. Token choisi pour Kobo. |

Les adresses `onrender.com` dépendent du nom des services. Si le nom est déjà pris, Render ajoute un suffixe. Relevez les adresses réelles après la création, puis corrigez `CORS_ORIGINS` et `REACT_APP_BACKEND_URL` si besoin (étape 4).

## 2. Créer les services avec le Blueprint

1. Fusionnez la branche `feature/detection-orpaillage-goh` dans `main` sur GitHub.
2. Render → **New** → **Blueprint** → choisissez le dépôt `AlphaCodant/GestAlert`, branche `main`.
3. Render lit `render.yaml` et demande les valeurs marquées « sync: false ». Collez celles de l'étape 1.
4. Cliquez sur **Apply**. Render construit l'API (2 à 4 minutes), puis l'interface (4 à 8 minutes).

## 3. Vérifier

- `https://gestpro-api.onrender.com/api/` doit répondre `{"app":"GestPro","status":"ok",...}`.
- Ouvrez `https://gestpro.onrender.com`, puis connectez-vous avec `admin@gestpro.ci` et le mot de passe choisi.
- Allez dans **Orpaillage (satellite)**. Le bandeau orange « Mode démonstration » ne doit plus apparaître. Le cadre « Nouvelle analyse » affiche « GEE · projet forestmonitoring-500922 ». Cliquez sur **Tester**.

## 4. Corriger une adresse

Service → **Environment** → modifiez la variable → **Save changes**.

| Variable modifiée | Ce qui se passe |
| --- | --- |
| Variable de l'API | Render redémarre l'API automatiquement. |
| `REACT_APP_BACKEND_URL` | Lancez **Manual Deploy → Clear build cache & deploy** sur le site statique. Cette valeur est intégrée au moment de la construction. |

## Points d'attention

- **Offre gratuite.** L'API se met en veille après 15 minutes sans visite. Le réveil prend environ 1 minute, et une analyse en cours peut être interrompue par la mise en veille. Pour un usage réel, passez l'API sur une offre payante dans Settings → Instance Type.
- **Clé GEE.** Ne la mettez jamais dans le dépôt. Collez-la uniquement dans la variable `GEE_SERVICE_ACCOUNT_JSON`.
- **Page « Analyse IA ».** Elle utilise le paquet privé `emergentintegrations`, qui n'est pas installé sur Render. Cette page affichera une erreur. Le reste de l'application n'est pas concerné.
- **Taille des analyses.** Privilégiez des zones de quelques centaines de km², comme Seriyo. Une analyse sur tout le Gôh peut dépasser les limites de mémoire de l'offre gratuite ou les quotas GEE.
