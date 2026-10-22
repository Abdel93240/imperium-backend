# Les 12 écrans et leurs parcours

Navigation principale : **Tableau de bord · Transactions · Catégories · Réglages**. Pas de treizième écran métier imposé : sous-formulaires, historique et aide restent intégrés aux surfaces correspondantes. Revenir conserve les filtres et la position de lecture.

## VAU-01 — Tableau de bord — vault/dashboard

Afficher le dernier relevé réel, sa date, le prévu séparément, les soldes cash/banque/crypto, la synthèse de la période, le dernier bénéfice professionnel hebdomadaire clôturé, la pression avec « Voir pourquoi » et les prochaines échéances. Une seule action principale : **+ Dépense**. **+ Gain** et **Scanner ticket** sont secondaires. Les cartes se chargent indépendamment. Au premier lancement : « Renseigner mes soldes » et « Ajouter une transaction ». Ne pas afficher 0 € pour un relevé inexistant. Lien vers VAU-10 pour vérifier le réel, VAU-11 pour les échéances, VAU-06 pour la pression.

La carte bénéfice affiche la semaine précise ; ne pas confondre le dernier résumé clôturé et la semaine en cours. Les balances pro/perso détaillées restent partielles tant que le contrat d'agrégation sur période ne les fournit pas : ne pas rebaptiser le net global « bénéfice pro ».

## VAU-02 — Ajouter un gain — vault/transactions/new-income

Feuille : montant EUR, libellé/description, catégorie proposée éditable, badge livre déduit, portefeuille, date/heure locale, note facultative. Type income fixe. Montant strictement positif avec deux décimales ; convertir le texte en centimes entiers sans calcul flottant. Catégories à charger depuis le serveur et filtrer par kind. Exemple fictif : 125,00 €, vtc, banque. Ne pas envoyer book, label ou total_eur comme champs de transaction : libellé utilisateur dans note, mapping du DTO documenté.

« Ajouter » sauvegarde un brouillon puis envoie une fois avec une clé stable. « Enregistré » seulement après réponse de création acceptée. Un double appui garde la même action. Montant invalide : erreur sous le champ, pas de perte de saisie. Hors réseau : « En attente de synchronisation ». Fermer une saisie non vide propose conserver ou abandonner.

## VAU-03 — Ajouter une dépense — vault/transactions/new-expense

Même structure que VAU-02, type expense fixe. Exemple : 45,20 €, carburant, cash, note « Station de démonstration ». Montrer la catégorie suggérée avant validation ; changement manuel prioritaire. « Autre » ne doit pas créer silencieusement une catégorie hors référentiel : garder un libellé dans note et choisir une catégorie réellement disponible, ou signaler la dépendance backend. Aucun champ de TVA, fiscalité ou provision automatique ajouté sans contrat.

Après succès, rafraîchir registre, résumé, wallet et pression à la demande. Si la mémorisation de la catégorie échoue après la transaction, ne pas recréer la transaction : résultat financier confirmé, apprentissage séparé.

## VAU-04 — Scanner un ticket — vault/receipts/capture

Caméra, galerie, import document pris en charge ; permissions au moment du besoin. Prévisualisation, reprendre la photo et « Saisie manuelle ». Contrôler taille et format avant envoi. Upload binaire brut, pas multipart ni base64 JSON. Écran de chargement commun pendant l'appel OCR synchrone ; aucun faux pourcentage. À l'échec, montrer le message lisible pendant 10 secondes puis revenir, sans effacer une saisie manuelle. Permettre de garder le message pour accessibilité. Hors réseau : photo en attente, aucune lecture OCR présentée comme faite. Une annulation locale du réseau ne prouve pas l'annulation côté serveur.

## VAU-05 — Vérifier le ticket — vault/receipts/{extraction_id}/review

À gauche ou en haut : vignette authentifiée. À droite ou en dessous : commerçant, date/heure, total, portefeuille, catégorie/livre, confiance et avertissements. Les valeurs incertaines sont visibles et corrigibles ; total manquant bloque la validation. Une dépense pour le total du ticket, pas une dépense par ligne.

Les lignes alimentaires ont une case d'inclusion dans Pulse, nom, quantité, unité, type/date limite si connus. Envoyer **stock_lines** correspondant exactement au choix final ; `[]` signifie aucun aliment. Omettre ou envoyer null déclenche les lignes alimentaires par défaut côté serveur : à éviter quand tout est décoché. Ne pas demander une deuxième validation dans Pulse.

Boutons « Valider », « Re-scanner », « Annuler ». Afficher succès seulement après réponse comprenant transaction et stock_items. État validated : reçu consultable, pas une nouvelle validation. État failed : message et reprise manuelle. État cancelled : pas de confirmation. Conserver l'identifiant pour reprise de GET, sans inventer de liste globale des tickets.

## VAU-06 — Comprendre la pression — vault/pressure

Score /100, libellé français, date du calcul, facteurs explicatifs, cash + banque disponibles, obligations, capacité de gains et objectifs minimum/confortable/optimal reçus. Historique horodaté, sans interpoler de faux points. « Voir pourquoi » appelle explain : pas besoin de modèle IA pour justifier un calcul déterministe.

Panneau « Corriger le contexte » : échéance reportée (identifiant, nouvelle date, raison), déjà prise en charge (identifiant, raison), semaine exceptionnelle (lundi de semaine, raison). Lister les corrections actives, permettre révocation et recharger pression/explication. Prise en charge corrige le calcul ; « Déclarer payée » dans VAU-11 crée l'écriture financière. Les deux ne sont pas équivalents.

## VAU-07 — Transactions — vault/transactions

Lignes : date, note/libellé, catégorie, badge pro/perso si connu, portefeuille, origine, montant signé à l'affichage, statut inverse si is_reversal. La valeur amount_cents reste positive dans le modèle. Pagination limit/offset, filtres type/catégorie/source/période, effacer filtres. Distinguer registre vide et aucun résultat. Dans le service actuel, count est le nombre de lignes de la page, pas le nombre total du registre. Charger la page suivante tant que count atteint limit ; une dernière page vide est possible.

Un filtre livre ou recherche textuelle locale doit dire « sur les éléments chargés » ; aucune somme de la page présentée comme total global. Pour des filtres globaux non exposés, désactiver la fonctionnalité en attendant le contrat. Appui ligne → VAU-08. Brouillons en attente identifiés à part, sans les ajouter aux totaux confirmés.

## VAU-08 — Détail et correction — vault/transactions/{transaction_id}/edit

Afficher les champs exposés, dates, source et références, pas un historique complet imaginaire. Action correction : préremplir les champs actuels, demander une raison d'au moins 3 caractères, envoyer seulement les changements. POST correct retourne original_transaction_id, reversal et corrected ; montrer le résultat puis relire.

Action annulation : dialogue « Annuler par écriture inverse » et raison. Aucune suppression définitive du ledger. 409 : expliquer déjà annulée/corrigée ou conflit, relire sans rejouer aveuglément. Les opérations gérées par une autre app peuvent refuser la correction ; donation sadaqa → Path. Ne pas déclarer une transaction annulée sur la seule présence d'un montant négatif visuel ou d'un champ non exposé.

## VAU-09 — Catégories — vault/categories

Référentiel groupé pro/perso et revenus/dépenses, statistiques depuis summary/categories sur période. Libellé français d'affichage distinct de la clé backend. Catégorie sélectionnée → VAU-07 filtré. Ne pas présenter un bouton renommage fonctionnel sans endpoint. Une catégorie inconnue est « Non classée », jamais pro/perso décidé par l'IA frontend. Tendance graphique seulement si vraies séries disponibles ; les totaux par catégorie ne sont pas une série temporelle.

## VAU-10 — Mettre à jour les soldes — vault/wallet/update

Relevé courant et horodatage, prévu cash/banque/crypto, prompt check_suggested, historique des relevés. Formulaire cash ≥ 0, banque éventuellement négative, crypto ≥ 0 en EUR. Total de saisie = aperçu, total confirmé = réponse du backend. Aucun appel à une banque ou exchange. Ne pas additionner other_wallets_cents au total principal. Un dépôt de cash en banque se traduit par relevés ajustés, pas un revenu + une dépense artificiels.

Après saisie explicite → POST snapshots avec clé stable ; garder l'ancien relevé visible jusqu'au succès. Au retour sur un formulaire resté ouvert longtemps, proposer relire les valeurs avant d'écraser avec une nouvelle déclaration. Ne pas promettre un verrou de version non exposé.

## VAU-11 — Dépenses à venir — vault/upcoming-expenses

Liste des échéances actives, en retard, payées ou désactivées selon réponses disponibles ; active=false n'est pas synonyme de payée. Le statut visuel se déduit de paid_at, active et due_date ; il n'existe pas de champ status à envoyer.

Ajouter/modifier : label_fr, amount décimal EUR, due_date, catégorie, wallet facultatif, mandatory, recurrence null/monthly/quarterly/yearly. Annuler une récurrence ou désactiver : dialogue clair, DELETE désactive. Pas de réglage reminder_days_before sans contrat.

« Déclarer payée » : confirmer montant, date et wallet ; appeler mark-paid UNE fois. La réponse contient expense, transaction et next_occurrence. Ne pas poster une deuxième transaction ni générer la prochaine date côté app. Correction de pression distincte via VAU-06. Aucune transaction de paiement avant confirmation réelle de l'utilisateur.

## VAU-12 — Réglages — vault/settings

GET settings : pourcentage sadaqa et marge en lecture, catégories, date dernier relevé, nombre d'échéances, dates des synthèses/pression, rows et completion. Les dates sont des calculs métier, pas une preuve de dernière synchronisation du téléphone : afficher fetched_at séparément.

Lignes vers VAU-09/10/11 et réglages sadaqa Path. Un lien inter-app indisponible explique « Ouvrir The Path pour modifier » sans créer de réglage local parallèle. Prévoir retour vers Vault après action Path. Identifiants et secrets ne sont jamais un widget du dashboard.

## États communs à tous les écrans

loading, empty, ready, error, offline, stale, pending, syncing, conflict et disabled. Cache daté + bannière réseau ; reprise contextuelle ; erreurs sous le champ ou la carte concernée ; aucun écran vide après timeout. Les changements de rotation, mise en arrière-plan et arrêt du processus conservent les brouillons validés localement, sans les prétendre enregistrés au serveur.
