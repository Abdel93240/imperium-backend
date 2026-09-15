# Topologie de l'infrastructure physique — Référence

> **Statut : TOPOLOGIE ACTIVE.** Décrit la répartition physique actuellement en
> service dans l'écosystème Imperium, y compris l'infrastructure Phase H. Ce
> document est la référence pour le déploiement physique/technique local uniquement
> (GPU, GGUF, quantification, SHA256, runtime, endpoint, systemd, mesures H3).
> Le mapping logique ROLE → modèle concret/version appartient exclusivement à
> `30_AI_ROUTING_AND_SCORING_POLICY.md` §3.

---

## 1. Vue d'ensemble

L'écosystème Imperium est réparti sur deux lieux physiques principaux.

CHEZ LE PÈRE
- Tower principale : orchestrateur, backend Imperium/FastAPI, PostgreSQL,
  infrastructure IA locale, Codex CLI, Claude Code, secret du kill switch et
  services systemd.
  - Tesla V100 PCIe 32 Go : `local_executor`.
  - Tesla P40 : réservée aux futurs services IA complémentaires ; elle ne porte
    aucun service produit actif à ce jour.
- Machine 2 : NAS et Plex / Jellyfin.

CHEZ L'UTILISATEUR
- Tablette Galaxy : apps et interface Imperium.
- Deuxième Tower i7 : machine personnelle, hors de l'écosystème Imperium.

Hostinger/VPS ne fait pas partie de la topologie active. Il ne constitue ni le
backend, ni une source de vérité, ni une migration planifiée.

---

## 2. Chez le père

### Tower principale — orchestrateur, backend et IA locale

La Tower principale est le nœud central actif d'Imperium. Elle réunit sur une
même machine physique :

- l'orchestrateur ;
- le backend Imperium (FastAPI) ;
- PostgreSQL ;
- l'infrastructure d'inférence IA locale ;
- Codex CLI et Claude Code pour les workflows de développement ;
- le secret de déverrouillage du kill switch ;
- les services systemd associés.

La V100 PCIe 32 Go héberge le `local_executor` de la Phase H. La P40 reste
réservée à de futurs services IA complémentaires et n'est pas à présenter comme
un service actif.

### Machine 2 — NAS et streaming

- NAS : stockage central des fichiers et médias de l'écosystème.
- Plex / Jellyfin : streaming média.
- Linux serveur.

---

## 3. Chez l'utilisateur

### Tablette Galaxy

- Appareil d'usage quotidien.
- Fait tourner les apps de l'écosystème.
- Interface principale de l'utilisateur avec Imperium.
- Appareil à protéger en priorité en raison de son accès aux fonctions et données
  sensibles de l'écosystème.

### Deuxième Tower i7

- Machine personnelle de l'utilisateur.
- Hors de l'écosystème Imperium.
- N'héberge ni orchestrateur, ni backend, ni service IA de production.

---

## 4. Hébergement externe

Le VPS Hostinger est retiré de la topologie active. Le backend Imperium, sa base
de données et l'orchestration sont déjà locaux, sur la Tower principale chez le
père. Hostinger ne doit donc pas être décrit comme un backend de production, une
source de vérité ou une étape de migration future.

---

## 5. Réseau

- **Tailscale** relie les machines de confiance de la topologie active : Tower
  principale, Machine 2/NAS, tablette, téléphone et autres clients autorisés.
- Il permet notamment l'accès distant au NAS et le déclenchement du kill switch
  depuis une machine autorisée.

> ⚠️ Point d'attention : la connexion internet chez le père est critique pour
> l'accès distant. En cas de panne, la Tower, le backend, l'orchestrateur,
> l'infrastructure IA et le NAS sont injoignables à distance. Cela ne signifie
> pas que les services locaux s'arrêtent ; Tailscale redevient disponible lorsque
> la connectivité revient.

---

## 5-bis. État et trajectoire de l'infrastructure IA

Le backend est déjà local. La V100 est installée et le `local_executor` Phase H
est déployé et validé au niveau de l'infrastructure. L'IA produit reste toutefois
désactivée : cette disponibilité technique n'autorise ni génération produit, ni
action canonique sans les validations backend et utilisateur prévues par les
contrats.

La P40 et ses éventuels services complémentaires ne sont pas actifs. À plus long
terme, l'infrastructure pourra évoluer vers un serveur GPU dédié ou multi-GPU,
puis vers un modèle local de classe ~70B. Aucun calendrier ferme n'est défini.

Cette fiche ne déclare pas la validation humaine de la Phase H terminée.

---

## 5-ter. Local executor — Phase H

### Modèle et endpoint actifs en infrastructure

- Modèle : `Qwen3.6-27B-Q6_K`.
- Fichier : `/opt/models/Qwen3.6-27B-Q6_K.gguf`.
- Source : `unsloth/Qwen3.6-27B-GGUF`.
- SHA256 :
  `ec1805fe87e6519c461c1ed2d179865464a875ed241032ead65a354f979cfe14`.
- Matériel : Tesla V100 PCIe 32 Go.
- Runtime : `llama.cpp`, exposé localement sur `127.0.0.1:8081`.

### Fiche de déploiement

- Répertoire llama.cpp : `/opt/llama.cpp`.
- Commit : `16378d93f94012d4228c8c7683adce3f286aee5d`.
- Version : `0.4.0-dev build 10905`.
- Compilation : architectures CUDA `70;61`, GCC 12 et compilateur CUDA
  `12.0.140`.
- Service : `imperium-executor.service`.
- Offload GPU : `-ngl 99`.
- Contexte global : 65 536 tokens ; `parallel 2`, soit 32 768 tokens par slot.
- Optimisations : Flash Attention et cache KV K/V `q8_0`.
- Observabilité : métriques activées et journald.
- Raisonnement de service : `--reasoning-budget 0` et
  `--reasoning-format deepseek`.
- Résilience et limites mémoire : `Restart=always`, `MemoryHigh=23G`,
  `MemoryMax=24G`.

Le backend cible l'exécuteur exclusivement par
`LOCAL_EXECUTOR_URL=http://127.0.0.1:8081`. Les drapeaux restent
`qwen_enabled=False` et `real_ai_enabled=False` : aucune activation IA produit
n'est effectuée par cette infrastructure. Aucun shadow slot n'est activé et
aucune entrée `ai_role_models` n'est insérée.

### Résultats de validation H3

- Sous charge : environ 23 892 MiB de VRAM, inférieur à 30 Go ; GPU à 98–99 % ;
  température stabilisée à 77–78 °C pendant 10 minutes.
- `/health` répond `200` une fois le modèle chargé ; `/metrics` expose les
  métriques Prometheus.
- Génération : environ 22,98 tok/s, dans la cible de 15–25 tok/s (**PASS**).
- Prefill : 5 996 tokens en environ 8 300,685 ms, soit environ 722,35 tok/s.
- Prompts de 16k et 30k : **PASS** sans OOM ; le Q6 est conservé et aucun
  fallback Q5 n'est requis.
- Pulse Mode A, JSON strict avec thinking désactivé : 10/10.
- WR pair verdict, Mode A JSON strict avec thinking désactivé : 10/10.
- Mode B natif : validé avec budget de thinking 1 000, raisonnement séparé dans
  `reasoning_content`, JSON final valide et `finish_reason=stop`.
- Déterminisme Mode B à température 0 : contenu et raisonnement byte-identical,
  3/3.
- Stop/start : port et VRAM libérés, redémarrage réussi ; `/health` retourne
  `503` pendant le chargement puis `200`.
- Reboot réel : démarrage automatique et modèle disponible en environ 114 s,
  inférieur à 3 minutes (**PASS**) ; warm restart en environ 63 s.
- Aucun événement `MemoryHigh`, `MemoryMax`, OOM ou `oom_kill` durant la
  validation. Le cgroup comptabilise le mmap/page-cache du GGUF comme mémoire
  fichier, ce qui doit être pris en compte dans l'interprétation des mesures.

H3.7 — le scénario backend `GpuServiceUnreachable/skip` reste **NON TESTÉ** :
le wrapper `toolbox.llm` est absent. Il ne doit pas être marqué PASS.

### Contrats de budget et de sortie

Il n'existe pas de `max_tokens` global. Les profils par slot définissent :
`context_max_tokens`, `thinking`, `thinking_budget_tokens`,
`output_max_tokens`, `output_contract`, `grammar_mode`, `timeout_s` et
`on_truncation`.

- **Mode A** : thinking désactivé et schéma strict.
- **Mode B** : thinking plafonné et raisonnement séparé.
- Le wrapper ne parse jamais le raisonnement.
- Une réponse avec `finish_reason=length` n'est jamais acceptée comme réponse
  partielle.
- Aucun auto-ajustement silencieux des budgets ou contrats n'est autorisé.

Le CORS est actuellement permissif, mais le serveur n'écoute que sur localhost.
Le MTP n'est ni activé ni validé.

---

## 5-quater. Services modèles complémentaires — état futur

Les autres specs parlent en termes génériques (« service OCR », « service de
transcription »). Le mapping logique de ces rôles et leurs candidats appartiennent
au doc 30 §3 ; ce document décrit uniquement leurs possibilités de déploiement physique. Ces services ne sont pas actifs dans la topologie actuelle ; ils restent
réservés à la P40 ou à une future infrastructure dédiée.

- Service OCR envisagé : modèle VLM local précis, par exemple PaddleOCR-VL-1.6
  ou GLM-OCR.
- OCR Bolt : le chemin primaire prévu reste la capture + OCR embarqué (ML Kit
  on-device, spec Vector §3.3). L'accessibilité Android n'est jamais utilisée,
  ni en lecture ni en action. Une contre-lecture locale future ne constitue pas
  un chemin temps réel.
- Service de transcription envisagé : faster-whisper large-v3 (français et
  arabe), avec vigilance sur l'arabe dialectal.
- Garde-fou langue envisagé : `fastText lid.176.ftz` sur CPU, hors ligne.

---

## 6. Implications pour les autres specs

- **Kill switch** : secret de déverrouillage = Tower principale (chez le père).
- **Vidéo VTC** : stockage = NAS = Machine 2 (chez le père).
- **Dossier projet enrichi** : médias lourds = NAS = Machine 2 (chez le père).

---

## 7. Points ouverts

- Éventuelle évolution vers un serveur GPU dédié ou multi-GPU.
- Éventuel modèle local de classe ~70B, sans échéance ferme.
- Ajouts matériels possibles (RAM, disque) sur la Tower principale.
- Onduleur et/ou solution de secours de connexion chez le père, compte tenu de
  la criticité de l'accès distant.
