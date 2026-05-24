# Générateur de devis intelligent — Architecture

> **Statut : SPEC / À implémenter plus tard.** Document d'architecture
> uniquement. Aucune implémentation lancée. À sortir le jour où la feature
> devient prioritaire.

---

## 1. Objectif

Outil de génération de devis pour clientèle directe (TikTok, particuliers,
sous-traitance entre chauffeurs). Calcule un prix cohérent à partir des données
réelles de rentabilité du chauffeur, ajusté par catégorie de véhicule et par
les contraintes réelles du métier (heure, retour à vide).

Remplace le calcul mental à l'arrache par un devis chiffré, modifiable,
traçable, et relié à la base clientèle.

---

## 2. Entrées (saisie utilisateur)

- **Type de prestation** : `course` ou `mise à disposition`
  - Si course : adresse départ + adresse dépôt
  - Si mise à disposition : adresse départ + durée (nombre d'heures)
- **Heure de prise en charge** (date + heure)
- **Catégorie de véhicule** : `Bolt` (base) / `Berline` / `Van` / `Moto`
- **Adresse de prise en charge**
- **Adresse de dépôt** (pour une course)

---

## 3. Logique de calcul du prix

### 3.1 Donnée de référence : le taux horaire
- Le prix de base s'appuie sur le **taux horaire réel** du chauffeur,
  **réutilisé depuis la data existante** (la donnée de rentabilité horaire déjà
  utilisée par l'assistant Victor pour décider d'accepter ou non une course).
- **NE PAS créer de nouvelle donnée.** Brancher sur l'existant.
- ⚠️ **À faire au moment de l'implémentation** : identifier précisément où et
  comment cette donnée est stockée (table, champ) — éventuellement via un audit
  Claude Code à ce moment-là. Pas avant.
- Le taux horaire varie selon la tranche horaire (ex. samedi 2h du matin ≈
  40-45 €/h). La granularité par tranche horaire vient de l'historique des
  courses (prix + heure de réalisation, déjà stockés dans l'écosystème VTC).

### 3.2 Catégorie = multiplicateur
- `Bolt` = prix de référence (multiplicateur 1.0), basé sur ce que le chauffeur
  fait habituellement sur les applis.
- `Berline` / `Van` / `Moto` = multiplicateurs au-dessus.
- **Tous les multiplicateurs sont des variables modifiables dans les réglages.**
  Valeurs à définir à l'implémentation.

### 3.3 Le retour à vide (course uniquement)
- Zone d'activité = Île-de-France. On compte toujours le **retour vers le centre
  de Paris**.
- Calcul : temps de trajet [adresse de dépôt → centre de Paris] à **l'heure
  d'arrivée estimée** (pas l'heure de départ).
- Ce temps de retour à vide entre dans le coût du devis (temps non rémunéré à
  compenser).

### 3.4 Calcul du temps de trajet
- **API : TomTom** (déjà repérée dans le projet GPS, tier gratuit suffisant pour
  usage personnel).
- Sert pour : (a) durée estimée de la course, (b) durée du retour à vide.
- Tenir compte de la tranche horaire (trafic nuit vs jour).

---

## 4. Sortie : le devis

- Bouton **« Générer le devis »** → produit un devis chiffré.
- Le devis est **modifiable** (négociation client, réductions ponctuelles).
- Une fois ajusté : bouton **« Devis validé »**.

### Sur validation du devis :
1. **Fiche client** : création ou mise à jour. Constitue une base clientèle
   exploitable (relances fêtes, promotions, fidélisation). → logique commerciale.
2. **Proposition d'ajout au calendrier** : « Ajouter au calendrier ? » → si oui,
   création d'une **mission** dans le système Imperium existant (calendrier +
   mission + suivi).

---

## 5. Catégories de véhicule — contexte

- **Bolt / base** : l'activité actuelle (Uber X / Bolt). Sert de référence prix.
- **Berline** : à venir avec le projet Lexus GS. Hors catégories des applis →
  clientèle directe (TikTok, particuliers).
- **Van** : sous-traitance avec un pote en Van. Devis + pourcentage
  d'intermédiation. (logique de commission à définir plus tard)
- **Moto** : sous-traitance avec un pote taxi-moto. Même logique.

---

## 6. Dépendances et intégrations

- **Data VTC existante** : taux horaire / rentabilité horaire, historique des
  courses (prix + heures), vraisemblablement déjà dans pgvector / l'écosystème
  Victor. → à cartographier à l'implémentation.
- **API TomTom** : routing + estimation trafic.
- **Système de missions / calendrier Imperium** : pour l'ajout post-validation.
- **Base clientèle** : à créer (fiche client) si elle n'existe pas déjà.

---

## 7. Réglages (variables configurables)

- Multiplicateur Berline
- Multiplicateur Van
- Multiplicateur Moto
- (Bolt = base, multiplicateur 1.0 implicite)
- Marge de sécurité avant prise en charge (ex. 30-45 min où on ne prend plus de
  course avant le RDV — impact sur la rentabilité horaire à intégrer)

---

## 8. Phasage proposé (ordre d'implémentation, le jour venu)

1. **Cartographie** : identifier la data existante (taux horaire, courses,
   schéma VTC) pour brancher dessus sans dupliquer. (audit Claude Code à ce
   moment-là)
2. **Squelette devis** : saisie + prix = taux horaire × multiplicateurs. Devis
   modifiable. Sans API trajet.
3. **Intelligence trajet** : intégration TomTom (durée course + retour à vide
   vers centre Paris à l'heure d'arrivée).
4. **Client + calendrier** : fiche client (data relance) + proposition d'ajout
   au calendrier comme mission Imperium.

---

## 9. Points ouverts à trancher à l'implémentation

- Valeurs exactes des multiplicateurs par catégorie.
- Granularité des tranches horaires pour le taux de référence.
- Logique de commission pour la sous-traitance Van / Moto.
- Le retour à vide se base sur l'heure d'arrivée estimée → dépend de la durée de
  course calculée (chaînage des deux appels TomTom).
- Format de stockage / réutilisation exacte du taux horaire existant.
