# 04 — Design, conduite et tablette

## Identité et composants

Le socle reprend le design system du dépôt. Fond `#06181E`, surface `#0F2730`,
surface secondaire `#173744`, accent cyan `#00D9E0`, texte principal `#EEFAFD`,
texte secondaire `#B6CCD2`, bordures `#214756`. Halo positif `#22D673`, négatif
`#FF4A4A`, présence/analyse blanc. Le token jaune historique existe dans les
annexes mais n'est pas un verdict de course autorisé (doc 33 prioritaire).

Montants alignés et chiffres tabulaires ; typographie lisible, tailles adaptatives.
Les couleurs ne suffisent pas : associer icône/forme et retour sonore distinct,
avec description d'accessibilité. Réglages son coupé et animations réduites.
En conduite, pas de texte narratif de scoring, pas de clignotement incessant.

Composants à mutualiser : SessionKpiCard, MoneyInput, RecommendationCard,
FreshnessChip, SyncStatusChip, DrivingModeIndicator, VectorHalo, PermissionRow,
PendingActionRow, ConflictPanel, EmptyState et ErrorWithRetry. Ce sont des noms
de composants proposés, pas des DTO réseau. Prévoir les états Storybook/Preview
équivalents sans rendre obligatoire un outil particulier.

## Téléphone et tablette

Téléphone : une colonne, actions accessibles au pouce, formulaires courts en
bottom sheets, clavier décimal adapté au français. Tablette à l'arrêt : navigation
latérale (environ 240dp si l'espace le permet), contenu central et panneau de
détail (environ 320dp). Les sheets peuvent devenir des panneaux de 480dp.
Ne pas imposer trois colonnes si l'écran réel ou le zoom texte ne les permet pas.

Mode paysage testé ; tailles tactiles de 48dp minimum et actions principales
plus larges en conduite. Aucun contenu essentiel sous les barres système, le
clavier ou une encoche. Tester font scale 200 %, lecteur d'écran, mode sombre,
contrastes effectifs et réduction des mouvements. Un nombre tronqué doit garder
son unité et rester consultable à l'arrêt.

## Mode conduite

D'après doc 59 §14.14 : activation automatique si session active et vitesse GPS
> 5 km/h pendant 5 s ; désactivation sous 3 km/h pendant 60 s. Toggle manuel.
Sans permission GPS : mode préparation, bannière explicite et activation manuelle
possible ; ne pas prétendre connaître le mouvement depuis Bolt.

La conduite réduit l'interface à une carte centrale sans sidebar. Une action
principale maximum. Les longues saisies, listes denses, réglages métier et le
sélecteur de captures sont différés. Dictée courte si disponible, puis
confirmation explicite ; sinon conserver un brouillon pour l'arrêt.

Ce mode est une adaptation d'interface, pas un moteur de stratégie. L'utilisateur
ne doit pas devoir lire un rapport pour agir. Aucun challenge, récompense ou
animation de célébration. L'état hors ligne/obsolète est plus visible que le halo.

## Fraîcheur du conseil

Doc 59 définit un cache de 15 minutes et une obsolescence après 30 minutes ou un
déplacement > 2 km. Pour le trou 15–30 minutes, ce dossier propose « À actualiser »
(décision d'interface explicite, pas un état serveur). Afficher la date dans tous
les cas : relatif sur carte, absolu dans le détail, timezone Europe/Paris.

Une donnée juste lue mais générée depuis longtemps ne redevient pas fraîche.
Sans GPS, utiliser l'âge connu sans inventer de déplacement. Aucun son positif
pour un résultat issu du cache. L'heure système du client ne doit pas produire
un âge négatif visible ; recharger si incohérente.

## Schéma de présentation à l'arrêt

```text
VECTOR                         Réseau · Sync
Session active                 Mode conduite [ ]
CA        Dépenses       Net de session
Progression cible (si définie) · durée

Dernier conseil : zone / raison / date / cache
Contexte non pris en compte (si présent)
                 [ Où aller ? ]
[ Gain ] [ Dépense ] [ Dépose ] [ Fin de session ]
Historique · Offres · Réglages (accès secondaires)
```

Les cartes futures Smart Fuel et HUD restent hors navigation V1.
Ne pas demander d'illustrations générées pour remplacer des icônes ou données.
