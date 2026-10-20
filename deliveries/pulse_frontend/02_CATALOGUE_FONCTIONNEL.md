# Catalogue fonctionnel complet

État établi à partir du code du dépôt le 20 octobre 2026.
« Codé » décrit une implémentation, pas une activation vérifiée en production.
Les préfixes des routes Pulse sont tous `/api/imperium/pulse`.

| Fonction | Comportement attendu | État / contrat |
|---|---|---|
| Accueil du jour | Repas confirmés, macros, eau, séances, péremptions et bannières | Codé : `GET /dashboard?day=` |
| Vue quotidienne légère | Dernière saisie du jour et indicateurs simples | Codé : `GET /today` |
| Historique agrégé | Synthèse du suivi sur la période acceptée par l'API | Codé : `GET /stats/summary` |
| Saisie quotidienne | Sommeil, énergie, fatigue, poids et suivi de séance selon schéma | Codé : `POST /entries`, `GET /entries`, `GET /entries/{id}` |
| Repas texte / manuel | Description, heure, macros facultatives ; brouillon éditable | Codé : `POST /meals/drafts` |
| Repas vocal | Transcription relue puis même brouillon avec source `voice` | Texte accepté ; transport audio Pulse non fourni par cette API |
| Repas photographié | Image envoyée à l'OCR, estimation et niveau de confiance | Codé sous disponibilité OCR : `POST /meals/photo-drafts` |
| Validation du repas | Corriger macros, choisir le décompte du stock, confirmer | Codé : `POST /meals/{id}/confirm` |
| Annulation du brouillon | Annuler une proposition avant confirmation | Codé : `POST /meals/{id}/cancel` |
| Historique des repas | Totaux du jour, repas sans macros, détail | Codé : `GET /meals?day=`, `GET /meals/{id}` |
| Estimation macros depuis texte | Estimation proposée, jamais silencieusement validée | Pas d'estimation automatique dans la route de brouillon actuelle |
| Hydratation rapide | +250/+500 ml ou volume manuel, heure facultative | Codé : `POST /hydration-logs`, `GET /hydration-logs` |
| Eau et stock | Décompter l'eau disponible selon choix utilisateur, afficher avertissements | Codé, `decrement_stock` dans la requête |
| Objectif hydratation personnalisé | Fourchette prescrite par le programme validé | Cible actuellement nullable ; ne pas inventer 2 L |
| Contraintes de jeûne | Bannière, blocage eau dans la fenêtre, avertissement repas | Codé côté backend à partir des données The Path |
| Inventaire alimentaire | Nom, quantité, unité, catégorie, emplacement, dates, origine | Codé : `GET/POST /food-stock`, `PATCH /food-stock/{id}` |
| Alertes de péremption | Distinguer DLC/DDM, ouvrir les produits concernés | Codé : `GET /food-stock/alerts` |
| Déclaration de stock | Prévisualiser un texte, corriger, valider les lignes | Codé : `/food-stock/declarations/preview`, `/food-stock/declarations` |
| Scanner placard/frigo | Photo, lignes proposées, corrections, validation ou annulation | Codé sous disponibilité OCR : `/food-stock/scans` |
| Stock depuis ticket Vault | Afficher les achats ajoutés par le ticket déjà validé | Contrat partagé Vault ; aucune seconde validation du ticket |
| Recettes personnelles | Ajout conversationnel, web/OCR, adaptations validées | Cible ; pas de CRUD recette Pulse dans le contrat courant |
| Menus hebdomadaires | Recettes selon stock, objectifs, contraintes et disponibilité | Cible ; solveur nutrition non exposé |
| Liste de courses | Manquants, retraits manuels, achats réconciliés avec le stock | Cible ; pas de route autonome exposée |
| Batch cooking | Préparation en mission Imperium, matières premières → portions prêtes | Cible ; interface avancée hors socle V1 |
| Planifier une séance | Titre, date, exercices, matériel, durée/intensité | Codé : `POST /workouts` |
| Modifier une séance | Modification avec version serveur courante | Codé : `PATCH /workouts/{id}` |
| Démarrer / suivre | État corporel, exercice courant, séries/répétitions et repos local | Codé : `POST /workouts/{id}/start` ; suivi intermédiaire local |
| Terminer / passer | Résultats, effort, durée réelle ; motif obligatoire si passée | Codé : `/complete`, `/skip` |
| Historique sportif | Séances planifiées, en cours, terminées ou passées | Codé : `GET /workouts`, `GET /workouts/{id}` |
| Matériel possédé | Ajouter et retirer avec notes ; doublons normalisés côté serveur | Codé : `GET/POST /equipment`, `DELETE /equipment/{id}` |
| Programme manuel | Programme actif, phase, semaine, objectifs, pause/reprise/fin | Codé sous flag : `/programs/current`, `/programs`, `/{id}/status` |
| Cibles hebdomadaires | Séries cibles par groupe, tolérance, volume planifié | Codé sous flag : `PUT /programs/{id}/targets` |
| Dette de volume | Montrer la dette et ses statuts renvoyés, sans calcul frontend | Codé sous flag, dans `/programs/current` |
| Adaptation P1 | Proposition, explication, accepter/refuser/modifier | Codé sous activation : `/proposals`, `/{id}/decision` |
| Génération du programme IA | Objectifs, contraintes, catalogue filtré, proposition validable | Cible P3, distincte de la création manuelle codée |
| Révision mensuelle | Progression, adaptation globale et phases validables | Cible P7 |
| Parc adapté au trajet | Trouver le matériel extérieur dans la continuité de la journée | Cible, arbitrage Imperium ; pas de carte Pulse autonome branchée |
| Mesures corporelles | Poids, masse grasse déclarée, tours, notes, historique | Codé : `/body-snapshots`, sous consentement body |
| Photo corporelle | Comparaison locale facultative, suppression locale | Locale uniquement ; tout champ photo backend est refusé |
| Douleur / gêne | Zone, côté, intensité, type, gêne, impact et séance liée | Codé : `/pain-logs`, sous consentement pain |
| Résolution / suppression douleur | Clore ou supprimer explicitement | Codé : `/{id}/resolve`, `DELETE` unitaire ou collectif |
| Demande de replan | Proposer puis transmettre après accord | Codé : `/pain-logs/{id}/replan` ; cooldown/conflits à respecter |
| Consentements | Texte versionné, accord séparé body/pain/medical, retrait | Codé : `/consents`, `/consents/{domain}` |
| Documents médicaux | Import brut, consultation, téléchargement authentifié, suppression | Codé : `/medical-documents` ; analyse automatique non active |
| Règles médicales manuelles | Proposition, citation/source, sévérité, échéance, activation contrôlée | Codé : `/medical-rules` et transitions |
| Extraction de résultats médicaux | Champs corrigibles, unités, références imprimées, contre-lecture | Cible P5, pas de tableau de biologie branchable dans cette version |
| Alertes santé | Afficher message serveur, accusé de lecture distinct de résolution | Codé : `/red-flags`, `/{id}/acknowledge`, `/{id}/resolve` |
| Tableau de signaux | Valeur, unité, fraîcheur, bande, facteurs et inconnues | Codé sous flag : `GET /board` |
| Ressenti rapide | Fatigue, humeur, stress, échelle de 1 à 5 | Codé sous flag : `POST /reports`, lecture/suppression |
| Journal des interventions | Déclencheur, date, résultat, feedback utile/inutile/manqué | Codé sous flag : `/sentinel/dispatches`, `/{id}/reaction` |
| Métriques techniques | Qualité des interventions et audit ; détails secondaires | Codé sous flag : `/metrics/summary` |
| Recommandations génériques | Repas, entraînement et utilisation du stock à la demande | Pas de route `/api/pulse/recommendations` implémentée |
| Nourrir l'IA | Importer des connaissances, suivre extraction, corriger et valider | Routes partagées `/api/ai/knowledge-inbox` ; traitement selon activation |
| Chat contextuel | Capturer intentions et proposer actions à confirmer | Interface cible partagée ; aucune route de chat Pulse dédiée |
| Notifications | Rappels utiles selon règles backend, préférences utilisateur | Intégration Android à vérifier ; aucun polling ne doit fabriquer une alerte santé |
| Montre connectée | Features dérivées, fonctionnement complet sans montre | Cible future ; pas de dépendance pour le socle |
| Paramètres scientifiques | Corpus versionné, revues et validation | Cible technique ; pas un éditeur clinique libre dans le frontend |

Les fonctions futures font partie de la vision complète. Elles doivent apparaître
dans la conception ou le backlog, sans être présentées comme disponibles au quotidien.
