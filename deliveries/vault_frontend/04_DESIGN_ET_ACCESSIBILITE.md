# Design, tablette et accessibilité

Référence : doc 59, fondations dans les annexes. Cible V1 la plus récente : Galaxy Tab S8 11 pouces **portrait**, sidebar gauche conservée, dimensions fluides. Les anciennes indications S10 Ultra paysage correspondent à une adaptation ultérieure. Téléphone : navigation basse et feuilles plein écran si nécessaire. Grande tablette : lecture/détail sur deux colonnes seulement quand l'espace suffit.

Respecter les couleurs, typographies, espacements et surfaces du design system fourni. Pas de refonte visuelle imposée, pas de logo inventé requis pour livrer. Utiliser des icônes Material cohérentes ; afficher un libellé accessible, même pour un bouton icône.

## Hiérarchie

- Un montant dominant par écran ; sur l'accueil, identifier explicitement relevé réel ou solde prévu.
- Montants alignés à droite et chiffres tabulaires ; formats `1 234,50 €`, `−45,20 €` avec libellé gain/dépense.
- Jamais vert/rouge comme seule information : signe, texte et icône complètent.
- Action principale dépense immédiatement accessible ; secondaire gain et scan. Pas de graphiques décoratifs avant les chiffres utiles.
- Cibles tactiles au moins 48 dp, espacement suffisant, texte extensible, contraste vérifié, TalkBack, focus clavier et ordre de lecture logique.
- Jauge pression 0–100 avec label, date et lien explication. Ne pas mettre un effet « live » sur un snapshot ancien.
- Wallet banque négatif : ligne explicite ; une barre empilée positive ne doit pas masquer le découvert.
- Aucune animation longue ni interaction exigeant une grande précision. En déplacement, favoriser capture courte/voix et report de la vérification à l'arrêt.

## Composants à mutualiser

MoneyDisplay, MoneyInput, CategoryPicker, BookBadge, WalletPicker, TransactionRow, SyncBadge, CachedDataBanner, PressureCard, UpcomingExpenseRow, ReceiptLineEditor, InlineError et ConfirmationDialog. Ils sont de présentation : aucune formule de pression ou stratégie financière dedans.

## Textes prêts à l'emploi

« En attente de synchronisation » ; « Enregistré » après confirmation ; « Dernière mise à jour : … » ; « Aucun relevé pour le moment » ; « Aucune transaction sur cette période » ; « Vérifier ton solde réel ? » ; « Cette catégorie reste à choisir » ; « Le service de lecture des tickets n'est pas disponible » ; « Cette action a déjà été traitée. Les données ont été actualisées. »

Ne jamais annoncer « Tu as mal dépensé », « Investis maintenant » ou une obligation religieuse calculée par le frontend.
