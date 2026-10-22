# Catalogue fonctionnel

Statuts : **C** = contrat présent dans le code ; **P** = couverture partielle ou dépendance externe ; **F** = évolution sans raccordement V1 vérifié. C ne signifie pas testé contre la production.

| ID | Fonction à produire | Écran | Statut / comportement attendu |
|---|---|---|---|
| FIN-01 | Résumé revenus, dépenses, net et nombre d'écritures sur période | VAU-01 | C : summary, données serveur |
| FIN-02 | Vue mensuelle des entrées/sorties et tendance | VAU-01 | C : summary/monthly ; mois sans ligne distinct d'une erreur |
| FIN-03 | Bénéfice professionnel de semaine clôturée | VAU-01 | C : weekly-summaries ; montrer semaine et computed_at |
| FIN-04 | Séparation pro/perso visible | tous | P : référentiel catégorie/livre ; pas de filtre book serveur sur le registre |
| FIN-05 | Saisie gain | VAU-02 | C : montant positif, type income |
| FIN-06 | Saisie dépense | VAU-03 | C : montant positif, type expense |
| FIN-07 | Suggestion catégorie selon libellé | VAU-02/03/05 | C/P : mémoire utilisateur, table, puis modèle local si inconnu ; editable |
| FIN-08 | Apprentissage catégorie validée | VAU-02/03 | C : confirm ; absence de garantie de déduplication à signaler |
| FIN-09 | Caméra, galerie ou document reçu | VAU-04 | C/P : upload brut ; OCR selon disponibilité ; maximum 25 Mio |
| FIN-10 | Vérification total/date/catégorie/paiement du ticket | VAU-05 | C : aucune dépense avant validation |
| FIN-11 | Sélection des aliments vers stock Pulse | VAU-05 | C : envoyer stock_lines explicite, vide si rien sélectionné |
| FIN-12 | Consulter et annuler un brouillon OCR | VAU-05 | C : get, image et cancel authentifiés |
| FIN-13 | Pression réelle 0–100 et objectifs financiers indicatifs | VAU-01/06 | C : score du backend uniquement |
| FIN-14 | Explication et historique de pression | VAU-06 | C : explain, history |
| FIN-15 | Corriger un contexte de pression et révoquer la correction | VAU-06 | C : postponed, handled, exceptional_week et raison |
| FIN-16 | Liste paginée, filtres de date/type/catégorie/source | VAU-07 | C : limit/offset ; aucune recherche globale inventée |
| FIN-17 | Détail et origine d'une transaction | VAU-08 | C : source, external_ref, dates, note, reversal |
| FIN-18 | Corriger une transaction | VAU-08 | C : POST correct, raison obligatoire ; original + inverse + corrigée |
| FIN-19 | Annuler une transaction | VAU-08 | C : POST reverse ; jamais DELETE du ledger |
| FIN-20 | Catégories et statistiques | VAU-09 | C : référentiel et summary/categories |
| FIN-21 | Catégories personnalisées, renommage, gestion mémoire | VAU-09 | P/F : pas de CRUD public identifié ; lecture et choix existants seulement |
| FIN-22 | Dernier relevé cash, banque, crypto et solde prévu | VAU-01/10 | C : snapshot et predicted séparés ; autres wallets hors total |
| FIN-23 | Saisir un relevé et lire l'historique | VAU-10 | C : snapshot idempotent ; banque négative permise |
| FIN-24 | Échéances ponctuelles et récurrentes | VAU-11 | C : création, modification, désactivation ; mois/trimestre/année |
| FIN-25 | Déclarer une échéance payée | VAU-11 | C : mark-paid crée dépense, clôture et éventuelle occurrence suivante |
| FIN-26 | Alertes échéances proches ou en retard | VAU-01/11 | P : données disponibles ; rappels backend selon activation des jobs |
| FIN-27 | Réglages et état de complétude | VAU-12 | C : settings en lecture, liens vers écrans propriétaires |
| FIN-28 | Lien sadaqa avec Path | VAU-01/12 | C/P : bénéfice et paramètres lisibles ; donation et réglages dans Path |
| FIN-29 | Origine des recettes/dépenses Vector | VAU-07/08 | C : backend écrit déjà ; ne pas recopier les montants |
| FIN-30 | Authentification, expiration, déconnexion | transversal | C : auth et appareils ; compte personnel existant |
| FIN-31 | Brouillons, cache daté, reprise réseau | transversal | Frontend : état local explicite et jamais vérité canonique |
| FIN-32 | Saisie vocale puis confirmation | VAU-02/03 | P : service transcription requis, aucun endpoint Vault dédié attesté |
| FIN-33 | Conseil détaillé et analyse mensuelle IA | VAU-06 | F : pas de route advice/detail présente ; explication déterministe disponible |
| FIN-34 | Export CSV/PDF et synchronisation bancaire/crypto | futur | F : aucun endpoint d'export vérifié ; banque/crypto automatiques V2 |
| FIN-35 | Bulle flottante déplaçable de saisie gain/dépense | transversal / VAU-12 | V1 frontend : permission volontaire, panneau court, même contrat transaction et état pending ; voir document 13 |

## Priorité de réalisation

P0 : authentification, résumé, saisie manuelle, registre, erreurs réseau et données financières exactes. P1 : soldes, échéances, pression, correction, catégories et bénéfice hebdomadaire. P2 : tickets et passage Pulse, liens Path/Vector, voix raccordée si contrat disponible. Les surfaces futures doivent rester isolées du fonctionnement quotidien.
