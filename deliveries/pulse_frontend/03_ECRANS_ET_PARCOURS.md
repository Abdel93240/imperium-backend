# Écrans et parcours

Conserver les quatorze identifiants PUL existants. Les programmes, consentements,
signaux et réglages s'insèrent dans des sous-vues, sans imposer une nouvelle
barre de navigation. Toutes les vues ont les états : chargement, vide, contenu,
erreur, hors ligne, synchronisation, conflit, fonctionnalité désactivée.

## PUL-01 — Aujourd'hui

- Date du jour de Paris et sélecteur de jour pour consulter l'historique.
- Bandeaux serveur en tête : alerte santé, jeûne, douleurs, stock et données incomplètes.
- Carte repas : nombre confirmé, kcal/protéines/glucides/lipides, compteur sans macros.
- Carte eau : total réel ; cible uniquement si renseignée par le backend.
- Carte séance : titre, heure, durée, intensité, statut, ouvrir/démarrer.
- Raccourcis : « Ajouter un repas », « Boire », « Noter une douleur », « Mesures ».
- Sommeil/énergie/fatigue de la saisie actuelle, avec accès au journal.
- Ne jamais afficher une note santé fictive. Masquer la jauge si `health_score=null`.
- Rafraîchir après une mutation ; préserver une saisie en cours lors du rafraîchissement.

Sous-vue Journal : utiliser les champs de `PulseEntryCreate`, sans supposer une
échelle identique aux signalements `/reports`. Sous-vue Signaux : `/board`,
valeur/unités/date/fraîcheur, état inconnu ou périmé explicite. Ressenti :
fatigue/humeur/stress de 1 (bien) à 5 (mal), affichage textuel évitant l'inversion.

## PUL-02 — Ajouter un repas

Trois entrées : texte, dictée transcrite et photo. La dictée exige une transcription
disponible puis relue ; `source=voice` ne signifie pas que l'API reçoit un audio.
Formulaire : description, heure du repas, libellé optionnel, macros optionnelles.
Texte non vide, 2 000 caractères maximum. Conserver le brouillon après une erreur.
Un appui crée un brouillon serveur et ouvre PUL-03. Une photo est envoyée en corps
brut, avec progression/attente, jamais convertie en faux JSON base64.
En indisponibilité OCR, proposer texte ou saisie manuelle.

## PUL-03 — Confirmer le repas

Afficher description, provenance, estimation, confiance et avertissements.
Champs éditables : libellé, heure et quatre macros. Une macro absente reste vide.
Stock : liste de propositions avec quantité/unité, confiance, case à cocher.
Les lignes peu fiables restent décochées ; une correspondance n'est pas une consommation.
Présenter « Tout utiliser » (`finish`) lorsque nécessaire. Expliquer le conflit
de stock insuffisant ; recharger la ligne et demander une nouvelle validation.
« Confirmer » produit le repas canonique et le décompte atomique.
« Annuler le brouillon » utilise la route d'annulation.
Une relance réseau réutilise exactement la clé et le corps initiaux.

## PUL-04 — Boire

Boutons +250 ml, +500 ml et saisie libre entière entre 1 et 5 000 ml.
Ces volumes sont des raccourcis d'interface, pas des objectifs médicaux.
Afficher l'heure, l'option de décompte du stock d'eau et le total confirmé.
Pendant un jeûne, afficher la contrainte renvoyée, respecter le refus backend.
Un enregistrement passé utilise son heure réelle. Une cible absente donne
« Objectif personnalisé non disponible », sans pourcentage calculé.
Chaque appui est une action distincte ; le retry d'un appui ne crée pas une seconde action.

## PUL-05 — Planifier une séance

Titre, date/heure, durée, intensité (`low|medium|high`), matériel.
Exercices : nom, séries, répétitions, durée en secondes, charge et notes facultatives.
Les champs de programme, type de séance et charge systémique restent avancés.
Validation selon `WorkoutCreate` ; ne pas mélanger `intensity` et `intensity_score`.
En modification envoyer `version` dans `WorkoutUpdate`.
Si la version est dépassée : montrer serveur/brouillon, ne pas écraser.
Lien mission facultatif fourni par le contexte Imperium ; aucune seconde mission active.

## PUL-06 — Séance en cours

Au démarrage : état corporel libre facultatif, puis appel `/start`.
Exercice courant avec grandes commandes séries/répétitions, notes et minuterie
de repos locale. Garder la progression locale pour survivre à une fermeture.
Il n'existe pas de route de sauvegarde de chaque série : envoyer `results` à la fin.
Exercice passé : motif obligatoire. Fin : durée réelle, effort de 1 à 10, notes,
résultats indexés sur les exercices. Séance passée : motif obligatoire.
Un chronomètre terminé ne marque pas automatiquement la séance accomplie.
Conflit serveur : comparer les états avant de proposer une résolution.
Une alerte bloquante remontée par le backend reste visible ; aucun bouton de
contournement implicite.

## PUL-07 — Proposition d'adaptation

Utiliser les propositions réellement présentées par `/proposals`.
Montrer `summary_fr`, contexte, changements lisibles disponibles dans `payload`,
échéance et état. N'inventer ni confiance ni comparaison lorsque ces champs manquent.
Accepter, refuser avec explication, modifier seulement avec des paramètres
autorisés et revalidés côté serveur. Pas d'éditeur JSON brut pour l'utilisateur.
Après décision montrer le résultat `applied`, puis recharger séance/programme.
Un `PROPOSAL_STALE` entraîne relecture et avertissement ; aucune application locale.
Une proposition dry-run reste invisible. Si le serveur ne fournit pas de menu
structuré de modifications, limiter l'UI à accepter/refuser et expliquer cette limite.

## PUL-08 — Mesures et évolution

Consentement body avant écriture. Date, poids, masse grasse déclarée, taille,
poitrine, bras, notes ; au moins une mesure. Valeurs et précision dans le contrat.
Historique chronologique, unités visibles, courbes sans projection ou verdict.
`weight_change_kg` est une différence observée, pas un score d'effort.
Photo facultative strictement locale, exclue des payloads, exports automatiques
et sauvegardes cloud de l'app. Prévoir refus de permission sans bloquer les mesures.
Supprimer un relevé ou tout l'historique après confirmation ; suppression globale
via `confirm=true`. Le retrait du consentement ne supprime pas automatiquement les données.

## PUL-09 — Douleur ou gêne

Consentement pain. Zone corporelle (liste contractuelle), côté, intensité 0–10,
type libre, limitation, impact sportif, séance liée et date.
Saisie courte ; un schéma corporel est une aide accessible, jamais le seul moyen.
Liste des douleurs en cours et résolues ; actions résoudre et supprimer.
Afficher `suggest_replan` et `replan_message` lorsqu'ils existent.
« Demander une replanification » requiert un appui explicite ; gérer
`REPLAN_COOLDOWN`, `REPLAN_ALREADY_OPEN`, `DAY_NOT_STARTED`, `PAIN_RESOLVED`.
Ne pas transformer le niveau de douleur en diagnostic local.

## PUL-10 — Repas et nutrition

Date, repas confirmés, macros du jour, informations manquantes. Ouvrir le détail
et créer un repas. Le contrat courant n'offre pas une correction générique d'un
repas déjà confirmé : ne pas ajouter un bouton « modifier » qui ne peut pas aboutir.
Sous-vues futures clairement identifiées : recettes, semaine alimentaire, courses,
portions préparées. Le journal quotidien n'attend pas le solveur nutrition.

## PUL-11 — Entraînement

Liste de séances par jour/statut selon paramètres API, détail et actions contextuelles.
Sous-vue Matériel : nom, notes, ajouter/retirer, retour d'un doublon existant.
Sous-vue Programme : programme actif, mésocycle, semaine courante, cibles,
tolérance, volume planifié et dette. Aucun programme → état vide explicite.
Créer manuellement, mettre en pause, reprendre, terminer et remplacer les cibles.
La création remplace le programme actif : afficher cette conséquence avant envoi.
Le remplacement des cibles envoie la liste complète de la semaine.
Ne pas présenter cette saisie comme une génération IA.

## PUL-12 — Stock

Liste avec quantité/unité, catégorie/emplacement disponibles, DLC/DDM, provenance.
Filtres d'affichage : à consommer, périmé, type/emplacement selon données renvoyées.
Ajouter, modifier avec version, indiquer consommé selon le contrat ; pas de DELETE
inventé. Un produit sans date n'a pas de durée de conservation estimée localement.
Déclaration textuelle : prévisualiser, corriger les lignes, valider.
Les arrivées depuis Vault apparaissent comme déjà confirmées par le cerveau commun.
Sous-vue « Courses » future sans mutation de stock déduite d'une case cochée.

## PUL-13 — Scanner placard ou frigo

Prise de photo ou sélection volontaire, permission caméra à la demande.
Upload, analyse, liste proposée, correspondances avec stock et doublons.
Correction des quantités/unités/dates, validation des lignes sélectionnées ou
annulation. Le scan seul ne modifie jamais l'inventaire.
Traiter aussi un état d'analyse échouée dans une réponse HTTP réussie.
Reprendre à partir du `scan_id` lorsque disponible ; pas de réupload automatique en boucle.

## PUL-14 — Santé et documents

Trois sous-vues : Documents, Règles actives, Alertes. Accès aux consentements
et à la suppression des données depuis le même espace.
Documents : type, date, nom, taille, statut, message et date de rétention.
Import après consentement medical général ET accord spécifique à cet envoi.
Afficher « Pulse ne pose pas de diagnostic ». L'état `uploaded` ne devient pas
« analysé » localement. Ouvrir le fichier via un téléchargement authentifié.
Règles : saisir texte, type, sévérité, citation, document source et échéance.
Avant activation, faire confirmer source relue, texte confirmé et validité ;
ajouter l'accord critique si requis. Proposer désactivation/remplacement/suppression.
Alertes : afficher le message backend, date et blocage éventuel.
« J'ai lu » (`acknowledge`) et « Résoudre » sont des actions distinctes.
La résolution utilise la raison contractuelle et une explication si nécessaire.
Ni l'acquittement ni un changement d'écran ne retirent un blocage automatiquement.

## Fonctions transversales

Connexion et session expirée ; connexion réseau ; file de synchronisation ;
recherche locale dans les listes déjà chargées ; paramètres d'accessibilité ;
gestion des autorisations ; lien Imperium ; capture « Nourrir l'IA ».
La gestion avancée de la sentinelle et des métriques reste dans les détails,
pas dans les premières cartes quotidiennes.
