# Dossier médical + fiche d'urgence (Pulse) — Architecture

> **Statut : SPEC / À implémenter plus tard.** Document d'architecture
> uniquement. Aucune implémentation lancée.

---

## 1. Objectif

Exploiter les nombreuses données de santé déjà présentes dans Pulse (sommeil,
hydratation, hormonal, constantes, etc.) pour deux usages concrets dans le monde
réel :

1. **Dossier médical complet** : un onglet qui agrège toutes les données santé
   dans un format clair, simple à présenter à un médecin / professionnel de santé.
2. **Fiche d'urgence** : les infos vitales accessibles en cas d'accident ou
   d'urgence médicale.

> Motivation renforcée : l'utilisateur fait ~80-90 h de route/semaine en VTC. Le
> risque d'accident n'est pas théorique → avoir ses infos vitales accessibles aux
> secours a une vraie valeur.

---

## 2. Principe directeur : DEUX niveaux distincts

Ne jamais confondre les deux — ils ont des besoins **opposés** :

| | Dossier médical complet | Fiche d'urgence |
|---|---|---|
| Contenu | Riche, détaillé, historique | Minimal, vital |
| Usage | Consultation posée | Secours en 5 secondes |
| Accès | **Très protégé** | **Ultra-accessible** |

> Le piège à éviter : faire partir « tout le dossier » en urgence. Un urgentiste
> n'a pas le temps de lire 40 pages — il veut les 5 lignes qui peuvent sauver.
> La fiche d'urgence est une **sélection volontaire et minimale**, pas un dump.

---

## 3. Fiche d'urgence : contenu

Court, vital, lisible immédiatement. Typiquement :
- Groupe sanguin
- Allergies (surtout médicamenteuses)
- Traitements en cours
- Pathologies majeures / antécédents critiques
- Personne(s) à contacter en urgence
- (éventuel) Don d'organes, directives particulières

---

## 4. Fiche d'urgence : accès — LES DEUX, mais activation à creuser

**Décision : accessible PAR LES SECOURS (sans l'utilisateur) ET déclenchable PAR
l'utilisateur.** Avec une **priorité claire** : l'accès autonome par les secours
est le plus important (couvre le pire cas : utilisateur inconscient après un
accident).

> Point critique soulevé par l'utilisateur : **trouver un bon moyen d'activation**,
> que ce soit par lui ou par les secours. C'est LA question délicate de cette
> feature. À creuser sérieusement à l'implémentation.

### Réflexion clé : ne pas réinventer un canal que personne ne cherchera

Les secouristes connaissent déjà la **fiche médicale native du téléphone**
(iPhone Santé / Android, accessible depuis l'écran verrouillé sans code). Si la
fiche d'urgence vit UNIQUEMENT dans l'app Pulse, un secouriste ne saura pas
qu'elle existe ni comment y accéder.

→ **Piste privilégiée** : Pulse **alimente / génère la fiche médicale native du
téléphone** (le canal standard que les secours connaissent), plutôt que de
réinventer un mécanisme isolé. Pulse reste la **source de vérité riche**, mais il
exporte les infos vitales vers le canal reconnu.

### Déclenchement par l'utilisateur (bonus, cas conscient)
- Via le chatbot / un bouton : « mode urgence médicale » → affiche la fiche
  d'urgence en premier plan.
- Utile quand l'utilisateur est conscient mais ne peut pas tout expliquer.
- ⚠️ Ne PAS en faire le seul moyen : en cas d'accident, l'utilisateur peut être
  inconscient et incapable de taper/parler. D'où la priorité à l'accès autonome.

> Moyens d'activation à étudier : fiche native écran verrouillé, QR code/NFC
> (ex. sur le téléphone ou un support dans le véhicule pointant vers la fiche),
> bracelet/carte d'urgence, etc. À trancher à l'implémentation.

---

## 5. Dossier médical complet

- Agrège les données santé de Pulse en une vue structurée, claire, présentable à
  un médecin.
- Remplace la reconstitution de mémoire de l'historique en consultation.
- **Accès très protégé** (voir section 6).
- Format à définir : export PDF présentable ? vue à l'écran ? les deux ?

---

## 6. Sécurité & RGPD (donnée la plus sensible de l'écosystème)

Les données de santé sont une **catégorie « spéciale » au RGPD** → protection
maximale.

- **Dossier complet** : accès strictement contrôlé, chiffrement, authentification
  forte.
- **Fiche d'urgence** : tension à gérer — doit être **facile d'accès** (secours)
  mais ne contenir que le strict vital. La séparation des deux niveaux (section 2)
  est ce qui résout cette tension : on expose peu, et seulement le vital.
- Données personnelles → restent dans l'écosystème de l'utilisateur ; tout appel
  externe (le cas échéant) se fait avec contexte anonymisé.

---

## 7. Dépendances et intégrations

- **Pulse — données santé** (existant) : source de toutes les données.
- **Fiche médicale native du téléphone** (iOS/Android) : canal d'accès secours
  privilégié (à alimenter depuis Pulse).
- **Chatbot Pulse** : déclenchement « mode urgence » par l'utilisateur.

---

## 8. Points ouverts à trancher à l'implémentation

- **Le moyen d'activation de la fiche d'urgence** (LE point clé) : fiche native
  écran verrouillé, QR/NFC, support dans le véhicule, etc. Trouver le bon
  équilibre accessibilité secours ↔ protection.
- Faisabilité technique d'alimenter la fiche médicale native depuis Pulse (API
  iOS Santé / Android).
- Contenu exact de la fiche d'urgence (liste définitive des champs vitaux).
- Format du dossier complet (PDF présentable, vue écran, export sécurisé).
- Mécanisme de protection/chiffrement du dossier complet.
- Que faire pour que les données restent à jour automatiquement depuis Pulse
  (synchro fiche ↔ données vivantes).
