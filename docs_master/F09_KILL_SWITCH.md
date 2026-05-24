# Kill switch / verrouillage d'urgence de l'écosystème — Architecture

> **Statut : SPEC / À implémenter plus tard.** Document d'architecture
> uniquement. Aucune implémentation lancée. Sécurité critique — précision
> requise à l'implémentation.

---

## 1. Objectif

Pouvoir **verrouiller tout l'écosystème à distance**, depuis n'importe laquelle
des machines Tailscale (Tower, PC Thomson, téléphone, tablette), en cas de
perte, vol ou compromission d'un appareil — en particulier la tablette (Galaxy
Tab) qui fait tourner les apps.

**Motivation** : l'écosystème accumule des données ultra-sensibles — dossier
médical, RIB et données financières (The Vault), etc. Si quelqu'un trouve le code
de la tablette ou la compromet, le volume de données exposées serait
catastrophique. Il faut un **kill switch**.

---

## 2. Principe : défense en couches

**Décision : les trois couches (API coupée + apps verrouillées + données
chiffrées), avec une PRIORITÉ ABSOLUE sur la couche VPS.**

### Couche 1 — Couper l'API côté VPS (LA plus importante)
- Les données vivent sur le **VPS**. En mode verrouillé, **l'API refuse toute
  requête**.
- Conséquence : n'importe quel appareil volé (tablette, téléphone) devient une
  **coquille vide**, même déverrouillé. C'est le cœur de l'efficacité du kill
  switch.
- Couvre le scénario principal (vol de la tablette).

### Couche 2 — Données chiffrées au repos
- Les données sensibles sont **chiffrées au repos** ; le mode verrouillé révoque
  / rend inaccessibles les clés.
- Objectif : même un accès root à la tablette ne donne rien d'exploitable en
  local (caches, données résiduelles).

### Couche 3 — Verrouillage des apps sur les appareils
- Les apps (tablette/téléphone) passent en état verrouillé.
- Couche la moins fiable seule (un attaquant ayant l'appareil peut tenter de
  contourner l'app) → **dissuasif/cosmétique**, vient en complément, jamais seule.

> Ordre de priorité si une seule chose devait être faite : **couper l'API VPS.**
> Le reste renforce.

---

## 3. Déclenchement

- **Depuis n'importe quelle machine Tailscale** : Tower, PC Thomson, téléphone,
  tablette.
- Une **commande** lance le verrouillage complet immédiat de toutes les
  applications / de l'accès aux données.
- Doit fonctionner même depuis un appareil de confiance restant si la tablette
  est déjà perdue.

---

## 4. Déverrouillage : secret HORS de la tablette

**Décision : déverrouillage via un secret stocké sur une machine sûre (PAS la
tablette).**

**Principe de sécurité non négociable** : *le secret de déverrouillage ne doit
JAMAIS vivre sur l'appareil qu'on cherche à protéger.* Sinon vol de la tablette =
vol du secret = kill switch inutile.

- Le secret vit sur une **machine sûre** : concrètement la **Machine 1
  (orchestrateur) située CHEZ LE PÈRE** (cf. spec Topologie de l'infrastructure).
  Hors du domicile de l'utilisateur → un cambriolage chez lui ne compromet pas le
  secret. Le VPS peut servir de secours.
- Idéalement combiné à une **phrase connue par cœur** par l'utilisateur
  (incorruptible physiquement — on ne peut pas voler ce qui est dans la tête).
- Le déverrouillage est une action **délibérée et difficile**, exécutée dans un
  **terminal** (pas un simple bouton).

---

## 5. Chemin de récupération (piège classique à éviter)

> ⚠️ Le piège n°1 des kill switches : **se verrouiller soi-même dehors.**

- Prévoir un **chemin de récupération fiable** : la commande de déverrouillage
  doit rester exécutable depuis une **machine sûre** (Tower / VPS en SSH) même
  quand tout le reste est verrouillé.
- Tester le scénario « je me suis verrouillé, je dois revenir » AVANT de se fier
  au système.
- Éviter tout point de défaillance unique qui rendrait le déverrouillage
  impossible.

---

## 6. Pièges de sécurité à garder en tête (implémentation)

- Secret de déverrouillage jamais sur l'appareil protégé (cf. section 4).
- Vérifier l'absence de données sensibles en cache clair sur la tablette (cf.
  couche 2).
- S'assurer que « API coupée » signifie vraiment **toutes** les routes de données
  (pas d'endpoint oublié qui fuit).
- Le canal de déclenchement (Tailscale) doit lui-même être sûr et authentifié.
- Penser au cas où le VPS est injoignable au moment du déclenchement.

---

## 7. Lien avec la sécurité globale de l'écosystème

Ce kill switch est une **brique de sécurité globale**, pas une simple feature.
Logique cousine d'autres protections déjà imaginées dans d'autres contextes
(ex. PIN de duress du concept de téléphone sécurisé). À terme, ces protections
pourraient être pensées ensemble — mais cette spec reste focalisée sur le kill
switch.

---

## 8. Dépendances et intégrations

- **Tailscale** : réseau de déclenchement entre machines de confiance.
- **VPS** : couche 1 (coupure API) + dépôt possible du secret de déverrouillage.
- **Tower** : machine sûre alternative pour secret / déverrouillage.
- **Apps (tablette/téléphone)** : couche 3 (état verrouillé).
- **Chiffrement au repos** : couche 2 (à mettre en place sur les données
  sensibles — Vault, médical, etc.).

---

## 9. Points ouverts à trancher à l'implémentation

- Mécanisme exact de la commande de déclenchement (script, endpoint
  authentifié, etc.) et son authentification.
- Comment l'API VPS bascule en « mode verrouillé » (flag global, middleware qui
  refuse tout, etc.).
- Schéma de chiffrement au repos et gestion/révocation des clés.
- Forme exacte du secret de déverrouillage (phrase + secret machine sûre).
- Procédure de récupération détaillée et testée.
- Comportement si le VPS est injoignable (file d'attente du verrouillage ?
  verrouillage local en attendant ?).
- Faut-il un verrouillage **automatique** sur signaux suspects (trop d'échecs de
  code, géoloc anormale) en plus du déclenchement manuel ?
