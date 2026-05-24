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
