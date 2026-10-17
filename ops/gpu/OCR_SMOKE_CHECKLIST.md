# Checklist de smoke — service OCR (rôle `ocr_service`, Tower)

> Exécution DIFFÉRÉE : se lance quand le service OCR tourne sur la Tower. Le backend
> est déjà prêt (app/services/ai/ocr.py) et né désactivé. Quand tout est vert :
> `OCR_ENABLED=true` dans `backend/.env` (action utilisateur) → Nourrir l'IA lit les
> PDF et les images au réveil suivant du job `ai.knowledge_inbox`.

Pré-requis : `OCR_BASE_URL=http://<ip-tailscale-tower>:8091` dans `backend/.env`
(8090 est pris par les embeddings). Le moteur OCR est un choix de la Tower : le
backend ne connaît que le contrat ci-dessous.

## 0. Contrat attendu par le backend

```text
GET  /health  → 200
POST /ocr     corps brut = le fichier (PDF, JPEG, PNG, WebP, HEIC)
              en-têtes : Content-Type (type MIME), X-Filename (nom encodé en URL)
              → 200 {"text": "texte extrait", "confidence": 0.0..1.0 | null, "pages": int | null}
POST /vision  corps JSON {"task": "pulse.kitchen_inventory_photo", "prompt": "<consigne complète>",
                          "image_base64": "...", "mime_type": "image/jpeg"}
              → 200 l'objet JSON strict demandé par la consigne (doc 37 §5.2 pour le stock)
```

`/ocr` :
- Un PDF à plusieurs pages renvoie tout le texte, pages séparées par une ligne vide.
- Le backend tronque à 100 000 caractères.
- Réponse non JSON ou sans `text` → la source est marquée « non lue » (pas de nouvel essai).
- Service injoignable ou délai dépassé (60 s, `OCR_REQUEST_TIMEOUT_SECONDS`) → l'élément
  repasse « À analyser » et sera repris au réveil suivant.

`/vision` :
- Exige un modèle de vision (identifier des aliments, pas seulement lire du texte).
- La consigne vient du backend (`app/services/ai/prompts/`, versionnée) : le service
  l'applique telle quelle et ne garde ni l'image ni la réponse.
- Réponse hors du format de la consigne → l'analyse est marquée « illisible » ;
  injoignable → message « Le service d'analyse ne répond pas ».

## 1. Service debout

- [ ] `curl http://<ip-tailscale>:8091/health` → 200
- [ ] Le port N'EST PAS joignable depuis une IP non-Tailscale
- [ ] Aucun fichier reçu n'est conservé sur la Tower après la réponse (vérifier le dossier de travail)

## 2. Lecture réelle

```bash
cd /opt/imperium-backend/backend
.venv/bin/python - /chemin/vers/un/ticket.jpg <<'EOF'
import sys
from pathlib import Path
from app.services.ai import ocr
path = Path(sys.argv[1])
result = ocr.recognize(path.read_bytes(), filename=path.name, content_type="image/jpeg")
print(result.confidence, result.pages)
print(result.text[:500])
assert result.text.strip(), "texte vide"
EOF
```
- [ ] Texte lisible sur un ticket de caisse photographié
- [ ] PDF scanné de 3 pages : les 3 pages sont dans `text`, `pages == 3`
- [ ] Image de 20 Mo : réponse en moins de 60 s

## 2 bis. Analyse d'image (scan du placard)

- [ ] Photo d'un frigo avec des œufs et du lait : `POST /vision` renvoie `structured_result.items`
      avec `name_fr`, `estimated_quantity`, `confidence`
- [ ] Photo floue : `image_quality` = `poor`
- [ ] Réponse en moins de 60 s

## 3. État des services

- [ ] `GET /api/health/services` → ligne « Lecture des images et PDF » verte
- [ ] Service arrêté → la ligne passe orange, l'API reste verte
