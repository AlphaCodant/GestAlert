"""Vérifie la connexion à Google Earth Engine avec la clé du compte de service.

Usage (depuis le dossier backend) :
    python scripts/verifier_gee.py chemin/vers/cle.json
ou, si GEE_PRIVATE_KEY_FILE / GEE_SERVICE_ACCOUNT_JSON est déjà défini dans .env :
    python scripts/verifier_gee.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
if len(sys.argv) > 1:
    os.environ["GEE_PRIVATE_KEY_FILE"] = sys.argv[1]

import orpaillage_gee as gee  # noqa: E402

if not gee.gee_configured():
    sys.exit("Clé introuvable ou invalide : indiquez le chemin du fichier JSON du compte de service.")
print("Compte :", gee.gee_identity())
try:
    print("Résultat :", gee.check_connection())
    print("OK : l'application peut utiliser Google Earth Engine.")
except Exception as e:
    print("ÉCHEC :", e)
    print("Vérifiez que le projet est enregistré pour Earth Engine et que le compte de service")
    print("a le rôle « Earth Engine Resource Viewer » (ou « Service Usage Consumer ») dans ce projet.")
    sys.exit(1)
