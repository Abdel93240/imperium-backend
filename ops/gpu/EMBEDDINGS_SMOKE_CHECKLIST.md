# Checklist de smoke — serving embeddings (J+2, à l'arrivée des GPU)

> Exécution DIFFÉRÉE : cette checklist se lance quand la P40 est montée et que
> `imperium-embeddings.service` tourne. Elle ne bloque pas le merge de la passe 0.
> Quand tout est vert : `EMBEDDINGS_ENABLED=true` dans `backend/.env` (action
> utilisateur) → le commit mémoire WR (memories.py, déjà codé et gated) s'active (levée de D5).

Pré-requis : `EMBEDDING_BASE_URL=http://<ip-tailscale-tower>:8090` dans `backend/.env`.

## 1. Service debout

- [ ] `systemctl status imperium-embeddings` → active (running)
- [ ] `curl http://<ip-tailscale>:8090/health` → 200
- [ ] Le port N'EST PAS joignable depuis une IP non-Tailscale (test depuis un réseau externe)

## 2. Dimensions = 1024 exactement (canon doc 38 §5.1 / migration 0032)

```bash
cd /opt/imperium-backend/backend
.venv/bin/python - <<'EOF'
from app.services.ai.embedding import embed
vecs = embed(["test de dimension du serving"])
assert len(vecs) == 1 and len(vecs[0]) == 1024, f"dims={len(vecs[0])}"
print("dims OK: 1024")
EOF
```
- [ ] dims OK: 1024

## 3. Latence batch 32 textes

```bash
.venv/bin/python - <<'EOF'
import time
from app.services.ai.embedding import embed
texts = [f"phrase de test numéro {i} pour la latence du batch" for i in range(32)]
t0 = time.monotonic(); embed(texts); dt = time.monotonic() - t0
print(f"batch 32: {dt:.2f}s")
assert dt < 15, "latence batch anormale pour une P40 Q8"
EOF
```
- [ ] batch 32 sous ~15 s (attendu ≈ 0.2 s/texte sur P40 Q8, doc 38 §11)

## 4. Cosinus de paires témoins (qualité sémantique)

```bash
.venv/bin/python - <<'EOF'
from math import sqrt
from app.services.ai.embedding import embed

def cos(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    return dot / (sqrt(sum(x*x for x in a)) * sqrt(sum(y*y for y in b)))

proches = embed(["il dort mal et rate ses missions", "le manque de sommeil fait échouer ses journées"])
lointains = embed(["il dort mal et rate ses missions", "la vidange du véhicule est faite"])
c_proche, c_lointain = cos(*proches), cos(*lointains)
print(f"paire proche: {c_proche:.3f} ; paire lointaine: {c_lointain:.3f}")
assert c_proche > 0.6, "paire proche sous le seuil attendu"
assert c_proche - c_lointain > 0.15, "séparation sémantique insuffisante"
EOF
```
- [ ] cos(paire proche) > 0.6 et écart proche−lointain > 0.15

## 5. Chaîne backend complète

- [ ] `health_check()` retourne True (`.venv/bin/python -c "from app.services.ai.embedding import health_check; print(health_check())"`)
- [ ] Un job runner avec le serving COUPÉ → `job_runs.status='skipped'`, `skip_reason='gpu_service_unreachable'` (jamais failed)

## 6. Levée de D5 (action utilisateur, après 1-5 verts)

- [ ] `EMBEDDINGS_ENABLED=true` + redémarrage backend
- [ ] Consigner la levée au journal des bascules (doc 76)
