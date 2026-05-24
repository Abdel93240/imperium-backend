# Dossier projet enrichi (Imperium) — Architecture

> **Statut : SPEC / À implémenter plus tard.** Document d'architecture
> uniquement. Aucune implémentation lancée. Enrichit l'onglet Projet existant
> d'Imperium.

---

## 1. Contexte : ce qui existe déjà

L'onglet Projet d'Imperium repose sur un acquis déjà documenté et validé (jusqu'à
~doc 50-51, à jour depuis avril) :

- **Hiérarchie de projets décidée par l'utilisateur** : il en active un certain
  nombre, laisse les autres en suspens. La création se fait rarement de façon
  triviale (saisie manuelle possible mais rare) → surtout via le **chatbot**.
- **Conversation-Driven Project Management** (déjà acté) : on discute avec le
  chatbot, les **décisions concrètes** sont détectées et viennent **modifier le
  projet** (avec validation utilisateur). Tout est stocké en vector memory pour
  que l'IA apprenne la façon de penser de l'utilisateur.
  - Exemple validé : « châssis Iveco Daily allongé » décidé avec GPT → ajouté
    automatiquement comme étape du projet camping-car, avec la raison et le lien
    vers la conversation.

**Cette spec NE redéfinit PAS cet existant.** Elle ajoute une couche par-dessus :
le **dossier projet riche**.

---

## 2. Objectif de cette feature

Quand on clique sur un projet, ne pas avoir juste une liste d'étapes, mais un
**véritable espace de travail / dossier complet** où l'on retrouve tout le
contexte vivant du projet.

**Le problème résolu (mot de l'utilisateur)** : ne pas jeter les idées dans une
boîte à idées où l'on perd « le génie du moment où le cerveau a fait un milliard
de liens entre toutes les choses ». Capturer le contexte vivant d'une idée, pas
juste son titre. Quand on rouvre un projet, on doit retrouver le POURQUOI, pas
seulement le QUOI.

---

## 3. Contenu d'un dossier projet

Le dossier projet est la **vue enrichie** d'un projet. On y retrouve :

1. **Les étapes** (dont celles ajoutées automatiquement via les discussions GPT —
   l'acquis Conversation-Driven déjà en place).
2. **Médias** : photos, vidéos, **liens commentés** (un lien + une explication de
   pourquoi il est là / ce qu'il apporte).
3. **Schémas Mermaid** : diagrammes (carrés, ronds, flèches, texte) pour se
   projeter, générés avec l'IA et éditables.
4. **Lien vers les conversations** qui ont nourri le projet (traçabilité du
   raisonnement).

> Résultat : à la réouverture d'un projet, on a tout le contexte — pas juste
> « châssis Iveco Daily », mais pourquoi, la discussion qui y a mené, les photos
> de référence, le schéma d'assemblage.

---

## 4. Schémas Mermaid : IA propose + éditeur

- **L'IA génère le Mermaid depuis la discussion** (« voilà comment je vois
  l'enchaînement des étapes ») — elle fait ~90 % du travail.
- **Un éditeur Mermaid** permet à l'utilisateur de retoucher : ajouter une bulle,
  une flèche, supprimer un élément, etc. **sans avoir à écrire le Mermaid à la
  main** (l'utilisateur ne code pas le Mermaid lui-même).
- Mermaid étant du **texte**, c'est idéal : stockage léger, versionnable,
  régénérable et modifiable par l'IA à la demande. Bien plus puissant qu'un
  dessin figé.

> Décision : l'IA propose, l'utilisateur édite via un éditeur visuel/assisté.

---

## 5. Stockage photos/vidéos : prévu pour le NAS (V4/V5)

**Décision : reporté en V4 ou V5.** On ne stocke PAS les médias maintenant. Mais
**on prévoit dès maintenant l'architecture** pour que le branchement soit trivial
le jour venu.

- **Cible de stockage** : un **NAS auto-hébergé** = **Machine 2, située chez le
  père** (cf. spec Topologie de l'infrastructure). PC récupéré reconverti, gros
  disque + SSD. Héberge aussi Plex/Jellyfin.
- **Pourquoi pas sur le VPS** : les vidéos sont lourdes → risque d'espace disque,
  de sauvegardes qui gonflent, de coût. Le VPS reste le cerveau, pas le entrepôt
  de médias.
- **Approche architecture à prévoir** : le dossier projet référence ses médias
  par un **pointeur / chemin abstrait** (pas un stockage en dur côté VPS), de
  sorte qu'au moment du branchement du NAS, il suffira de pointer vers lui.
  - Images légères : éventuellement tolérables ailleurs, à décider.
  - Vidéos : systématiquement sur le NAS (le jour venu).

> Concrètement maintenant : on conçoit le modèle de données « média de projet »
> avec une indirection (référence + emplacement), prêt à accueillir le NAS. On ne
> connecte rien tant que le NAS n'existe pas.

---

## 6. Articulation avec l'existant

Le dossier projet enrichi se **branche sur** le Conversation-Driven Project
Management déjà documenté :

```
Projet (vue enrichie = "dossier projet")
├─ Étapes
│   ├─ saisies manuellement, OU
│   └─ ajoutées auto via discussion GPT (existant, avec validation)
├─ Médias (photos / vidéos / liens commentés)   → stockage NAS en V4/V5
├─ Schémas Mermaid (IA propose + éditeur)
└─ Conversations liées (vector memory, traçabilité du raisonnement)
```

---

## 7. Points ouverts (UI notamment)

- **Organisation de l'interface du dossier projet** : l'utilisateur n'a pas
  encore d'idée arrêtée sur l'UX. Objectif : un truc clair, réutilisable, avec un
  plan lisible qu'on agrémente au fil du temps. → à concevoir.
- Modèle de données « média de projet » avec indirection (prêt pour le NAS).
- Type d'éditeur Mermaid (librairie front à choisir, édition assistée vs édition
  texte avec preview).
- Quels liens commentés / comment les présenter.
- Comment afficher proprement le lien étape ↔ conversation source.

---

## 8. Phasage

1. **(existant)** Conversation-Driven Project Management : étapes + décisions
   auto + vector memory. Déjà documenté/acté.
2. **Dossier projet — structure + Mermaid + liens commentés** : la vue enrichie,
   schémas générés par l'IA et éditables, liens. Stockage médias en pointeur
   abstrait (pas de fichiers lourds encore).
3. **(V4/V5) Médias lourds via NAS** : branchement du NAS auto-hébergé pour
   photos/vidéos. Architecture déjà prévue en phase 2 → simple raccordement.
