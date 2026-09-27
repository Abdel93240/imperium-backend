# Checklist de smoke — local_executor (Phase H)

> Infrastructure uniquement. Cette checklist ne constitue pas une activation
> produit. `qwen_enabled=False` et `real_ai_enabled=False` restent inchangés.
> Aucun shadow slot ni seed `ai_role_models` n'est autorisé par cette validation.
>
> Référence technique : `docs_master/F10_TOPOLOGIE_INFRA.md` §5-ter.

## 1. Identité des artefacts

- [ ] Modèle présent : `/opt/models/Qwen3.6-27B-Q6_K.gguf`
- [ ] SHA256 :
  `ec1805fe87e6519c461c1ed2d179865464a875ed241032ead65a354f979cfe14`
- [ ] Checkout `/opt/llama.cpp` au commit :
  `16378d93f94012d4228c8c7683adce3f286aee5d`
- [ ] `llama-server --version` correspond au build documenté dans F10.

Le SHA256 complet est volontairement hors smoke courant : son calcul prend
environ 54 s sur la Tower.

Commande de contrôle :
    sha256sum /opt/models/Qwen3.6-27B-Q6_K.gguf

## 2. Service et configuration déployée

- [ ] `imperium-executor.service` est `enabled` et `active`.
- [ ] Le serveur écoute uniquement sur `127.0.0.1:8081`.
- [ ] La configuration systemd déployée correspond à
      `ops/systemd/imperium-executor.service`.
- [ ] Le drop-in mémoire déployé correspond à
      `ops/systemd/imperium-executor.service.d/memory.conf`.
- [ ] `MemoryHigh=23G` et `MemoryMax=24G`.
- [ ] `LOCAL_EXECUTOR_URL=http://127.0.0.1:8081`.
- [ ] `qwen_enabled=False`.
- [ ] `real_ai_enabled=False`.

## 3. Smoke automatisé reproductible

Depuis la racine du dépôt :

    python3 ops/gpu/local_executor_smoke.py

Le smoke valide :

- [ ] H3.2 `/health` → HTTP 200.
- [ ] H3.2 `/metrics` → HTTP 200 et réponse non vide.
- [ ] H3.5-bis Mode B natif : thinking plafonné, `reasoning_content` séparé,
      JSON final valide et `finish_reason=stop`.
- [ ] H3.6 Mode B température 0 : contenu et raisonnement byte-identical, 3/3.
- [ ] H3.5 Pulse Mode A : schéma JSON strict, thinking désactivé, 10/10.
- [ ] H3.5 WR pair verdict Mode A : schéma JSON strict, thinking désactivé,
      10/10.
- [ ] Sortie finale : `LOCAL_EXECUTOR_SMOKE=PASS`.

## 4. Validations H3 manuelles / mesures consignées

Ces validations ne sont pas simulées par `local_executor_smoke.py`.
Leurs résultats de référence sont consignés dans F10 §5-ter.

- [ ] H3.1 charge 10 min : VRAM ≈ 23 892 MiB, sous 30 Go ;
      température stabilisée à 77–78 °C.
- [ ] H3.3 génération ≈ 22,98 tok/s, cible 15–25 tok/s.
- [ ] H3.3 prefill : 5 996 tokens en ≈ 8 300,685 ms,
      soit ≈ 722,35 tok/s.
- [ ] H3.4 prompt 16k sans OOM.
- [ ] H3.4 prompt 30k sans OOM.
- [ ] Q6 conservé ; aucun fallback Q5 requis.
- [ ] Aucun événement `MemoryHigh`, `MemoryMax`, OOM ou `oom_kill`
      pendant la validation.

## 5. Résilience infrastructure

- [ ] Stop : processus arrêté, port libéré et VRAM libérée.
- [ ] Start : `/health` peut retourner 503 pendant le chargement puis 200.
- [ ] Warm restart : modèle disponible en ≈ 63 s lors de la validation H3.
- [ ] Reboot réel : service revenu automatiquement et modèle disponible
      en ≈ 114 s, sous la limite de 3 minutes.

### H3.7 backend — NON TESTÉ

Le scénario backend `GpuServiceUnreachable/skip` est **NON TESTÉ** car le
wrapper `toolbox.llm` n'existe pas encore.

Il ne doit pas être marqué PASS, simulé ou implémenté par anticipation pendant
cette passe infrastructure.

## 6. Points explicitement hors validation

- MTP : non activé, non validé.
- CORS : permissif actuellement, mais serveur lié uniquement à localhost.
- Aucun `max_tokens` global : les budgets appartiennent aux profils par slot.
- Aucun auto-ajustement silencieux des budgets ou contrats.
- Aucun parsing du raisonnement par le futur wrapper.
- `finish_reason=length` ne constitue jamais une réponse partielle acceptable.
- Aucune activation produit à l'issue de cette checklist.
- La validation humaine Phase H n'est pas déclarée terminée par cette checklist.
