# Enregistrement vidéo des sessions VTC (protection juridique) — Architecture

> **Statut : SPEC / À implémenter plus tard (cible V7).** Document d'architecture
> uniquement. Aucune implémentation lancée.

---

## 1. Objectif

Enregistrer et sauvegarder ce qui se passe dans l'habitacle pendant les sessions
VTC, pour disposer d'une **preuve en cas de litige ou de fausse accusation**.

**Motivation** : protection juridique. Cas réel ayant inspiré la feature : une
fausse accusation d'agression sexuelle, où seule une vidéo a permis d'innocenter
la personne. Pour un chauffeur transportant des inconnus, c'est une protection de
bon sens. Probabilité faible, conséquences potentielles très graves → on s'en
protège.

---

## 2. Principe : acquisition calée sur la session VTC

- L'enregistrement **démarre au début de la session VTC** et **s'arrête à la
  fin** — réutilise le fait que l'écosystème sait déjà quand une session
  commence/finit.
- Caméra orientée **habitacle**.
- Pas d'enregistrement hors session (proportionnalité + économie de stockage).

---

## 3. Choix matériel : PAS des lunettes Meta

L'idée initiale (« lunettes Meta ») n'est pas adaptée à un enregistrement continu
de plusieurs heures :
- Autonomie très insuffisante (dizaines de minutes).
- Doivent être portées ; l'angle suit la tête.

**Recommandation** : une **caméra fixe type dashcam orientée habitacle** :
- Alimentation continue (allume-cigare / USB véhicule).
- Angle stable sur l'habitacle.
- Conçue pour l'enregistrement longue durée en boucle.

> À l'implémentation : étudier le matériel disponible (dashcam habitacle, ou
> solution caméra + acquisition reliée à l'écosystème).

> ⚠️ **Bien sélectionner le matériel — point critique pour le stockage.** Même
> en achetant du matériel chinois bon marché (acceptable), VÉRIFIER absolument :
> - le **codec** utilisé (privilégier H.265/HEVC ; éviter les vieux codecs type
>   Motion-JPEG qui gonflent énormément les fichiers) ;
> - les **réglages de la caméra** (bitrate/débit configurable, résolution
>   réglable en 360p, enregistrement en boucle).
> Un mauvais codec ou un bitrate trop élevé peut **doubler, voire tripler** la
> taille des fichiers à qualité égale, et fausser tout le dimensionnement du
> stockage. Le matériel détermine directement combien d'heures tiennent sur le
> NAS.

---

## 4. Format et compression

- **Résolution : 360p suffit.** Le but est de prouver qu'il ne se passe rien
  d'anormal dans l'habitacle, pas de filmer en haute définition. Basse réso =
  beaucoup moins de stockage.
- **Bon codec de compression** (ex. H.265/HEVC) pour stocker un gros volume
  (l'utilisateur travaille beaucoup, longues sessions).
- Objectif : pouvoir conserver de nombreuses heures sans saturer le stockage.

---

## 5. Indexation : par les données VTC (+ timestamp)

**Décision : indexation par les données VTC** (course, trajet, heure), pas
seulement un timestamp brut.

- Timestamp horaire comme base technique (retrouver « 23h47 » dans un bloc de
  10h).
- **+ lien avec les données de course existantes** : pouvoir dire « la course
  vers Porto-Comte de cette nuit » et retrouver directement le segment vidéo,
  parce qu'Imperium connaît déjà l'heure de cette course.

> Avantage unique : la vidéo n'est pas un silo opaque, elle est **reliée à
> l'activité VTC**. En cas de litige sur une course précise, on retrouve le
> segment en quelques secondes au lieu de scroller des heures de vidéo.

---

## 6. Conservation : rétention limitée + exception incident (RGPD)

**Décision : conservation X jours puis suppression automatique, SAUF si la
session est marquée « à conserver » (incident).**

- Un litige émerge généralement dans les jours/semaines suivant une course → pas
  besoin de garder des années.
- Suppression auto après le délai = stockage maîtrisé (le NAS ne sature jamais)
  ET conformité (conservation proportionnée et limitée).
- **Exception** : en cas d'incident, l'utilisateur marque la session « à
  conserver » → elle échappe à la suppression auto.
- Durée exacte (X jours) à fixer à l'implémentation, idéalement avec un juriste.

---

## 7. Cadre juridique (RGPD / droit à l'image)

> ⚠️ Ni Claude ni cette spec ne sont une source juridique. À valider avec un
> professionnel le jour de l'implémentation. Points connus à anticiper :

- Filmer des passagers en France/UE touche au **RGPD** et au **droit à l'image**.
  Ce n'est pas interdit mais c'est **encadré**.
- **Informer les passagers** qu'ils sont filmés (ex. autocollant visible
  « véhicule sous vidéosurveillance »).
- Enregistrement **proportionné** à son but (protection juridique).
- **Conservation limitée** (cf. section 6) et **usage restreint** (preuve en cas
  de litige, pas de diffusion).

> La politique de rétention limitée (section 6) sert aussi la conformité.

---

## 8. Stockage : sur le NAS auto-hébergé

- Les vidéos vont sur le **NAS auto-hébergé** = **Machine 2, située chez le père**
  (cf. spec Topologie de l'infrastructure). **Pas sur le VPS** (volume trop lourd).
- Avantage : données vidéo sensibles hors du domicile de l'utilisateur.
- Cohérent avec l'architecture de stockage déjà prévue pour le dossier projet
  (indirection / pointeur vers le NAS).

**Dimensionnement (ordre de grandeur) :** en 360p H.265 (~0,5-1 Go/h), 4 To
permettent ~4000 à 8000 h d'enregistrement. Charge de travail réelle de
l'utilisateur : **~80-90 h/semaine** (≈ 350-390 h/mois). Sans rétention, 4 To
tiendraient ~10-20 mois. **Avec la rétention limitée (section 6), on ne stocke
qu'un ou deux mois glissants** → 4 To est très largement suffisant, et sur un NAS
de 16 To la vidéo ne prend qu'une fraction de l'espace. Le calcul réel dépend du
codec/bitrate du matériel choisi (cf. section 3).

---

## 9. Sécurité (données sensibles)

Données particulièrement sensibles (vidéo de personnes, finalité juridique) :
- **Accès restreint** au stockage des vidéos.
- **Chiffrement** souhaitable (ces données ne doivent jamais fuiter).
- Traçabilité des accès si possible.

---

## 9 bis. Partage de preuve : lien sécurisé depuis le NAS (PAS YouTube)

**Besoin** : pouvoir transmettre facilement le segment vidéo d'une course précise
en cas de litige (à une plateforme VTC, un avocat, les autorités).

**Décision : partage sécurisé depuis le NAS. PAS d'upload sur YouTube.**

Flux cible (réutilise l'indexation par course de la section 5) :
1. Sélectionner la course concernée dans le replay/vector.
2. Générer un **lien de partage temporaire** vers le segment vidéo, **protégé par
   mot de passe** et **avec expiration** (et **révocable**).
3. Envoyer ce lien.

> Avantages vs YouTube :
> - La donnée **reste chez l'utilisateur** (pas de transfert RGPD de visages de
>   passagers vers Google / serveurs hors UE).
> - Lien réellement contrôlé (temporaire, protégé, révocable) — contrairement au
>   « non répertorié » YouTube, accessible par quiconque a le lien.
> - La **preuve reste le fichier original horodaté non altéré** (valeur probante
>   préservée ; un upload YouTube affaiblit la valeur de preuve car « montable »).
> - Pas de risque de suppression de compte / de contenu par la plateforme.

> ⚠️ Pourquoi PAS YouTube (même privé/non répertorié) :
> - Transfert de données personnelles de tiers vers une plateforme externe →
>   responsabilité RGPD très alourdie.
> - « Non répertorié » = accessible par toute personne ayant le lien (pas un
>   coffre-fort).
> - Valeur de preuve juridique douteuse (contenu potentiellement monté/coupé).
> - Risque de suspension de compte (usage non prévu) et de suppression du contenu.

> Technique : la plupart des solutions NAS (ex. OpenMediaVault) ou un petit
> service maison savent générer des liens de partage temporaires protégés. À
> détailler à l'implémentation.

---

## 10. Dépendances et intégrations

- **Système de sessions VTC** (existant) : déclenche début/fin d'enregistrement.
- **Données de course / trajet** (existant) : pour l'indexation.
- **NAS auto-hébergé** : stockage (V4/V5 pour le NAS ; cette feature en V7).
- **Matériel caméra habitacle** : à choisir.

---

## 11. Points ouverts à trancher à l'implémentation

- Matériel exact (dashcam habitacle vs autre solution).
- Durée précise de rétention (avec juriste).
- Mécanisme technique d'acquisition (caméra autonome qui exporte vers le NAS,
  ou flux relié à un appareil de la voiture).
- Format de l'index vidéo ↔ course (comment lier un segment à une course).
- Chiffrement et contrôle d'accès du stockage vidéo.
- Modalité d'information des passagers (autocollant, mention).
- Marquage « à conserver » : UI et déclenchement (manuel, ou auto si signalement).
- Mécanisme exact du lien de partage temporaire sécurisé depuis le NAS
  (génération, mot de passe, durée d'expiration, révocation).
