# Design et accessibilité

## Navigation proposée pour la génération

Cinq destinations : Aujourd'hui (PUL-01), Repas (PUL-10), Sport (PUL-11),
Stock (PUL-12), Santé (PUL-14). C'est une composition proposée des écrans existants.
Mesures, douleurs, eau, ajout et confirmation s'ouvrent en sous-vues ou feuilles.
Sur téléphone : barre inférieure. Sur tablette : rail latéral et deux colonnes
liste/détail lorsque l'espace le permet. Respecter retour système, clavier,
rotation et conservation des brouillons.

## Palette Pulse issue du design système

| Usage | Couleur |
|---|---|
| Fond | `#1A0A0D` |
| Surface | `#2A1015` |
| Surface secondaire | `#3A1A20` |
| En-tête | `#3D1418` |
| Secondaire | `#682430` |
| Accent | `#FF8C7A` |
| Bordure | `#4A222B` |
| Succès confirmé | `#34C759` |
| Avertissement | `#F5A524` |
| Erreur | `#E5484D` |
| Information | `#0091FF` |

Prendre les textes et typographies dans l'annexe design. Vérifier le contraste
des combinaisons réellement employées ; un jeton ne garantit pas tous les usages.
Inter pour les informations courantes, chiffres tabulaires ou JetBrains Mono
pour mesures et macros si les polices sont disponibles ; police système en secours.
Ne pas faire dépendre le fonctionnement d'une police distante.

## Composants réutilisables

- Carte du jour et carte séance.
- Carte macros avec source, estimation, confiance et champs absents.
- Ligne de stock avec quantité, unité et date.
- Action eau, total réel et cible optionnelle.
- Exercice avec résultats, bouton passer et motif.
- Proposition avec changements disponibles et décision.
- Bannière serveur, état vide, état désactivé, réessayer.
- Badge de synchronisation et panneau de conflit.
- Consentement avec texte versionné.
- Document médical, règle, alerte et confirmation de suppression.
- Signal avec unité et fraîcheur, sans utiliser la seule couleur comme signification.

## Ergonomie pratique

Actions principales larges, cibles tactiles d'au moins 48 dp, libellés explicites.
Limiter les champs visibles à ceux nécessaires ; unités toujours proches des nombres.
Préserver la taille système du texte, TalkBack, ordre de focus et clavier adapté.
Décimales françaises à la saisie, conversion contractuelle au transport.
Les données inconnues utilisent « Non renseigné » ; le nombre zéro garde sa signification.
Pas de carrousel automatique, graphiques décoratifs ou rappels culpabilisants.

La saisie vocale réduit la friction lorsqu'elle est disponible. Les interactions
longues et le traitement des documents s'effectuent à l'arrêt. Un mode compact
peut afficher les informations déjà reçues sans demander de remplir un formulaire.

## Animations

Transitions brèves, respect de la réduction des animations. Aucun écran
bloquant de célébration. Le vert et le libellé « Enregistré » sont réservés à
la confirmation backend ; un brouillon local affiche « En attente d'envoi ».
