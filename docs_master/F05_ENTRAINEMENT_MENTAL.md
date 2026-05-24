# Module d'entraînement mental (Pulse) — Architecture

> **Statut : SPEC / À implémenter plus tard.** Document d'architecture
> uniquement. Aucune implémentation lancée. À sortir le jour où la feature
> devient prioritaire.

---

## 1. Objectif

Ajouter à Pulse un volet **entraînement mental**, en complément de
l'entraînement physique déjà en place. Des séances courtes de « gymnastique
cérébrale » suivies dans le temps comme les autres constantes de l'utilisateur.

Pulse suit déjà le corps (sommeil, hydratation, hormonal, entraînement
physique). Ce module ajoute le cerveau.

---

## 2. Promesse HONNÊTE (cadrage important)

**Ce que le module fait** : entretenir et stimuler des compétences cognitives
**directement utiles** à la vie de l'utilisateur, et observer leurs liens avec
le reste de sa santé.

**Ce que le module NE promet PAS** : « augmenter le QI » ou « rendre plus
intelligent ». Le consensus scientifique actuel est que l'entraînement cognitif
améliore surtout la performance **sur l'exercice pratiqué** (effet spécifique),
le transfert vers une intelligence générale étant faible ou débattu (cf. cas
Lumosity, condamné pour publicité mensongère).

> ⚠️ Domaine évolutif : vérifier l'état récent de la recherche au moment de
> l'implémentation plutôt que de se fier à une synthèse datée.

---

## 3. Principe directeur : le « transfert direct »

On contourne le débat sur le transfert vers le QI en ciblant des compétences qui
**SONT** celles que l'utilisateur emploie réellement :

- **Calcul mental** (ex. estimer une course VTC, gérer des chiffres d'entrepreneur)
- **Résolution de problèmes / énigmes**
- **Mémorisation** : retenir vite ET retenir longtemps
- **Concentration / attention soutenue** (tenir une longue session de conduite,
  de code, de travail)

> Logique : même si l'entraînement reste spécifique, ce qu'on entraîne = ce dont
> on se sert vraiment. C'est du transfert DIRECT (compétence utile), pas du
> transfert espéré (QI global).

---

## 4. L'avantage unique : corrélation avec les autres constantes Pulse

C'est ce qui justifie de construire ce module DANS Pulse plutôt que d'utiliser
une app de brain training externe.

Les scores cognitifs deviennent des **constantes Pulse** comme le reste, et l'IA
peut les **corréler** avec les données déjà présentes :

- « Tes scores d'attention chutent après une nuit courte »
- « Ta mémoire de travail est meilleure les jours où tu t'es entraîné physiquement »

Aucune app du marché ne peut faire ça pour l'utilisateur personnellement, parce
qu'elle n'a pas accès à son sommeil / hydratation / hormonal / entraînement.

---

## 5. Format des séances

- Séances **courtes** (~5-10 min), comme une séance physique mais pour le cerveau.
- Exercices répartis sur les grandes fonctions ciblées (calcul, problèmes,
  mémoire, concentration).
- **Suivi des scores dans le temps** → alimente les constantes Pulse.

---

## 6. D'où viennent les exercices

**Décision : chercher l'open source validé D'ABORD.** À l'implémentation,
première étape = recherche de bibliothèques d'exercices cognitifs existantes,
validées, et réutilisables proprement (licence, format, qualité scientifique).

Seulement si rien de correct n'existe : coder soi-même quelques exercices
simples mais bien conçus et scientifiquement fondés (ex. tâche « n-back » pour la
mémoire de travail — simple à implémenter, base scientifique réelle).

> Ne PAS générer des exercices « de a à z » avec un module IA sans base validée.
> Même esprit que les autres features : on s'appuie sur de l'existant solide.

---

## 7. Extension du module « Objectifs »

Pulse possède déjà un module où l'utilisateur classe ses objectifs **par ordre
de priorité**. Ce module sert à l'IA locale pour construire le prompt envoyé à
GPT pour l'entraînement physique (ex. objectifs : maigrir/voir ses abdos,
retrouver son cardio, etc.).

**On étend ce pattern au mental.** Intention de design : **deux sections
distinctes**, chacune priorisée indépendamment :

- **Objectifs physiques** (par priorité) → nourrit le prompt d'entraînement physique
- **Objectifs mentaux** (par priorité) → nourrit le prompt d'entraînement mental
  (ex. : améliorer le calcul mental, mémoriser plus vite, tenir la concentration
  plus longtemps)

> Justification du « deux sections » : ce sont deux entraînements différents qui
> génèrent deux prompts différents. « Maigrir » et « améliorer mon calcul mental »
> ne se comparent pas dans une même liste de priorités.

> ⚠️ À vérifier à l'implémentation : la structure réelle du module Objectifs
> existant. Décider alors si on le DUPLIQUE (deux modules) ou si on l'ÉTEND avec
> un champ « type » (physique/mental). L'intention reste : deux listes priorisées
> séparément, peu importe la mécanique sous le capot.

---

## 8. Réglages

- Section **« Entraînement mental »** dans les réglages (parallèle à
  l'entraînement physique).
- Paramètres à définir : fréquence des séances, durée, fonctions cognitives à
  prioriser (dérivées des objectifs mentaux), difficulté.

---

## 9. Dépendances et intégrations

- **Pulse — constantes** : les scores cognitifs s'ajoutent aux constantes suivies.
- **Module Objectifs existant** : à étendre (section mentale).
- **IA locale + prompt GPT** : même chaîne que l'entraînement physique (objectifs
  priorisés → IA locale → prompt structuré).
- **Bibliothèque d'exercices** : open source validée (à identifier) ou exercices
  maison en dernier recours.

---

## 10. Points ouverts à trancher à l'implémentation

- Recherche et choix de la bibliothèque d'exercices open source (étape 1).
- Structure du module Objectifs existant → duplication ou champ « type ».
- Quelles fonctions cognitives exactement, et quels exercices pour chacune.
- Système de scoring des exercices (comment quantifier une perf pour en faire
  une constante suivie).
- Vérifier l'état récent de la recherche sur l'entraînement cognitif avant de
  figer la promesse et le choix des exercices.
