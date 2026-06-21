# Topologie de l'infrastructure physique — Référence

> **Statut : RÉFÉRENCE D'ARCHITECTURE.** Décrit la répartition physique des
> machines de l'écosystème. Les autres specs renvoient à ce document plutôt que
> de répéter ces informations. Cible : réorganisation à venir (pas immédiate).

---

## 1. Vue d'ensemble

L'écosystème est réparti sur **trois lieux physiques distincts**, ce qui est un
atout de sécurité : pas de point unique de défaillance physique.

```
CHEZ LE PÈRE                CHEZ L'UTILISATEUR        HÉBERGÉ (Hostinger)
├─ Machine 1 :              ├─ Tablette Galaxy        └─ VPS
│   Orchestrateur +         │   (apps, usage           (backend de prod :
│   secret kill switch      │    quotidien)             FastAPI, n8n,
├─ Machine 2 :              └─ Tower i7-4790 32 Go      PostgreSQL, Docker)
│   NAS + Plex/Jellyfin         (machine perso,
                                 hors écosystème)
```

---

## 2. Chez le père (les deux machines récupérées)

Deux PC récupérés, reconvertis, qui **restent physiquement chez le père**.

### Machine 1 — Orchestrateur + secret kill switch
- Fait tourner le **bot orchestrateur** (Python async), **Codex CLI** (login
  ChatGPT Plus), **Claude Code** (login Claude Pro), PostgreSQL local, service
  systemd.
- Héberge le **secret de déverrouillage du kill switch** (cf. spec kill switch).
- Linux serveur uniquement (pas de Windows).
- > Specs précises à fournir ; choisir la plus costaude des deux machines pour ce
  >  rôle (Codex / Claude Code aiment la RAM en pic). Ajout RAM/disque possible.

### Machine 2 — NAS + streaming
- **NAS** : stockage central — vidéos VTC, médias des projets (photos/vidéos),
  fichiers.
- **Plex / Jellyfin** : streaming média par-dessus le NAS.
- Linux serveur.

> Avantage sécurité : le **secret kill switch ET les données sensibles (NAS)**
> sont hors du domicile de l'utilisateur. Un cambriolage chez lui ne compromet ni
> le secret ni les données.

---

## 3. Chez l'utilisateur

### Tablette Galaxy
- Appareil d'usage quotidien, fait tourner les **apps** de l'écosystème.
- **C'est l'appareil à protéger** en priorité (cf. kill switch) : il contient
  l'accès aux données sensibles (médical, Vault/finances).

### Tower (i7-4790, 32 Go RAM)
- **Sort de l'écosystème.** Le SSD Linux de l'orchestrateur est retiré ; la Tower
  est ramenée chez l'utilisateur et redevient sa **machine perso sur le côté**.
- N'héberge plus aucun rôle de l'écosystème.
- > Raison : surdimensionnée pour le seul bot orchestrateur, qui consomme très
  >  peu. Mieux vaut une machine récupérée dédiée et libérer la Tower.

---

## 4. Hébergé (Hostinger)

### VPS
- **Backend de production** : FastAPI (`imperium-api`), n8n, PostgreSQL, Docker,
  nginx, traefik.
- Source de vérité des données ; cœur du kill switch (couper l'API = couche 1).

---

## 5. Réseau

- **Tailscale** relie toutes les machines de confiance (Machine 1, Machine 2,
  tablette, téléphone, VPS, etc.) en réseau privé.
- Permet le déclenchement du kill switch depuis n'importe quelle machine, l'accès
  au NAS à distance, etc.

> ⚠️ Point d'attention : avec orchestrateur + NAS + secret chez le père, la
> **connexion internet de chez le père devient critique** pour l'écosystème. Si
> elle tombe, bot et NAS injoignables (Tailscale reprend proprement au retour).
> Non bloquant, mais à garder en tête.

---

## 5-bis. Phases temporelles de l'infra IA

L'infrastructure IA évolue en quatre phases. Ne pas les confondre.

Phase 1 — actuelle (GPU non reçus). Backend Imperium sur VPS Hostinger. Aucune
IA locale.

Phase 2 — bientôt, transitoire (GPU reçus, quelques jours). Les GPU (V100 32 Go
+ P40 24 Go) sont branchés sur la Tower i7-4790 pour TEST et mesure. La Tower
tourne à son maximum, alimentation 850 W (plafond, pics à décaler). Backend toujours
sur Hostinger. But : valider que les modèles tournent avant l'achat du serveur.
Embedding en Q8 sur la P40 (mode pont).

Phase 3 — cible (~novembre, fin de l'abonnement Hostinger). Achat d'un serveur
dédié GPU (Supermicro 4028GR-TRT, ou config montée EPYC 7532 / carte mère SP3 /
Corsair AX1600i, alimentation 1600 W). Migration de TOUT (Hostinger → serveur local) :
backend et IA locale réunis sur une seule machine. Ajout de la 2e V100, embedding en
FP16. C'est à partir de cette phase que le §3 devient vrai : la Tower sort de
l'écosystème et redevient la machine perso de l'utilisateur.

Note de dimensionnement : le serveur cible a de la marge au-delà du besoin d'Imperium.
Imperium peut tourner sur moins. Le surdimensionnement est un choix d'opportunité, pas
une exigence d'Imperium.

Phase 4 — certaine, lointaine : modèle local 70B. Passage à un modèle local ~70B
(Qwen 70B), nécessitant PLUSIEURS cartes Tesla récentes (au-delà des V100/P40). Raison :
finesse, précision et qualité de conversation supérieures au 32B. Cette phase arrivera
dans tous les cas, indépendamment des performances du 32B — amélioration prévue, pas
repli. Pont de secours (conditionnel) : SI le Qwen 32B se révèle insuffisant (scoring
ou conversation) AVANT que la phase 4 soit prête, bascule temporaire sur Sonnet (cloud)
en attendant. Collecte d'exemples d'entraînement et LoRA éventuel : hors topologie,
voir doc 74.

## 5-ter. Allocation GPU et modèles

Valable dès la phase 2 (Tower), puis sur le serveur en phase 3.

- V100 32 Go : Qwen 32B (Q5) seul. Le FP16 de l'embedding est réservé à la 2e
  V100 (phase 3).
- P40 24 Go : embedding qwen3-embedding:8b (Q8) + service OCR + service de
  transcription + OCR Bolt léger. Les 4 modèles restent résidents en permanence (pas
  de décharge/recharge) ; les pics d'utilisation ne sont jamais simultanés.
- Store de travail éphémère (vectorisation de session) : sur pgvector, voir doc
  38 §7-bis.
- Alimentation : 850 W en phase 2 → 1600 W en phase 3.

## 5-quater. Services modèles (document PROPRIÉTAIRE des noms concrets)

Les autres specs parlent en termes génériques ("service OCR", "service de
transcription"). SEUL ce document nomme les modèles concrets. Changer de modèle =
une ligne à modifier ici, aucun autre doc cassé.

- Service OCR = modèle VLM local précis (PaddleOCR-VL-1.6 ou GLM-OCR), sur la P40.
  Pour tout l'OCR du système (documents, médical, PDF).
- OCR Bolt (cas particulier, modèle DÉDIÉ distinct du service OCR système) :
  l'assistant d'acceptation de course lit D'ABORD le texte affiché via l'accessibilité
  Android (lecture seule, jamais d'action — voir règle Bolt). Si échec/blocage → OCR
  de capture avec PP-OCRv4 (léger, rapide), dédié à cet assistant.
- Service de transcription = faster-whisper large-v3 (français ET arabe), sur la
  P40. (large-v3 requis pour l'arabe.) Vigilance : arabe dialectal moins fiable.
- Garde-fou langue = fastText lid.176.ftz (CPU, ~1 Mo, hors-ligne, aucun impact
  GPU). Détecte les dérives massives de langue sur les artefacts conservés → drapeau →
  régénération ou validation utilisateur. OUVERT/évolutif : escalade possible
  (split-lang) si des contaminations ponctuelles passent au terrain.

---

## 6. Implications pour les autres specs

- **Kill switch** : secret de déverrouillage = Machine 1 (chez le père).
- **Vidéo VTC** : stockage = NAS = Machine 2 (chez le père).
- **Dossier projet enrichi** : médias lourds = NAS = Machine 2 (chez le père).

---

## 7. Points ouverts

- Specs précises des deux machines récupérées (à fournir) → choix de l'attribution
  orchestrateur vs NAS selon la puissance.
- Éventuels ajouts matériels (RAM, disque) sur la machine orchestrateur.
- Calendrier de la réorganisation (pas immédiat).
- Onduleur / sauvegarde de la connexion chez le père ? (vu la criticité — à
  évaluer plus tard).
