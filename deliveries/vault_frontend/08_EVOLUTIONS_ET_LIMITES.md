# Évolutions, dépendances et limites explicites

## À préparer sans prétendre le raccordement réalisé

- Filtres globaux par livre, portefeuille et recherche de libellé : contrat liste actuel insuffisant. Un filtrage de page n'est pas une recherche exhaustive.
- Soldes/balances pro/perso en direct par période : ne pas les substituer au net global du résumé. Le bénéfice de semaine clôturée existe.
- CRUD de catégories personnalisées, renommage et édition de mémoire : pas de route publique identifiée. Conserver référentiel en lecture et choix existants.
- Conseil détaillé local et analyse mensuelle : rôles logiques des docs 30/42 ; pas de `/api/vault/advice/detail` présent. « Voir pourquoi » reste fonctionnel via explain déterministe.
- Pipeline vocal complet : capture centrale et transcription_service à raccorder ; pas de validation automatique depuis l'audio.
- Navigation inter-app Path/Pulse/Imperium : adapter les liens à l'application hôte réellement générée ; aucun schéma d'URI externe ne doit être présenté comme déjà installé.
- Export CSV/PDF : besoin possible, hors contrat actuel. Prévoir backlog, pas un faux téléchargement d'un historique limité.
- Liste/recherche générale des justificatifs et historique enrichi de corrections : ne pas prétendre ces API présentes à partir du seul GET d'un identifiant.

## V2 ou plus tard

Synchronisation de comptes bancaires et exchanges, cours crypto et multi-devises ; type transfert avec sémantique comptable propre ; détection d'échéances depuis emails ; prévisions avancées clairement séparées du réalisé ; analyse mensuelle cloud sur demande ; suivi carburant intelligent via Vector et non moteur financier parallèle ; export fiscal si cadré ultérieurement.

L'analyse de la Weekly Review appartient à Imperium/WR. Les anomalies financières peuvent y alimenter une vue filtrée ; ne pas créer un dossier autonome de décisions Vault. Aucun investissement automatique ou contrôle des dépenses n'est autorisé, même dans un écran futur.

## Dépendances opérationnelles

Routes présentes ≠ migrations appliquées ≠ job activé ≠ modèle OCR accessible. Les jobs de la fondation ont été initialement désactivés. Le générateur doit prévoir indisponibilité, dernier calcul daté et correction manuelle. La disponibilité runtime doit être vérifiée avant production sans modifier ici le backend en cours de travail.
