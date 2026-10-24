# 07 — Règles métier et intégrations

## Prière

Cinq prières obligatoires : fajr, dhuhr, asr, maghrib, isha. Horaires de la mosquée de référence MAWAQIT si cache valable, sinon calcul backend. Une seule mosquée de référence, choisie explicitement. La proximité ne l'active jamais. La qualité et la source accompagnent chaque vue. « Non marquée comme accomplie » reste une déclaration de statut neutre ; une prière sans ligne n'est ni échec ni accomplissement.

## Jeûne

Le début demande un choix explicite du type. Suhoor/iftar et contrainte d'hydratation viennent de `fasting/state`. Pulse reçoit la contrainte via backend ; The Path n'écrit pas le journal alimentaire. Rupture et annulation d'erreur sont des flux différents. Le calendrier peut suggérer un jour blanc, jamais démarrer un jeûne.

## Sadaqa ↔ Vault

The Vault fournit le bénéfice professionnel hebdomadaire réel. The Path applique son pourcentage et sa marge côté backend, puis reporte le reste. Afficher séparément bénéfice, source (`vault_summary/live/snapshot`), cible de base, report, dons, restant et nombre de transferts Vault en attente. La saisie d'un don peut créer une dépense personnelle Vault via backend ; si le transfert échoue, le don Path reste confirmé et le statut `pending` est visible. Le bouton retry appelle uniquement l'endpoint Path. L'annulation du don crée la contrepassation prévue par le backend ; le client ne supprime pas une transaction Vault directement.

## Ghusl ↔ Imperium

Seul l'utilisateur active le signal. Le backend peut créer ou demander une mission/replanification. Montrer `replan_status` tel quel ; ne jamais annoncer une mission active si seul un événement est en attente. Terminer avec l'ID de l'état lu. Imperium conserve la règle d'une mission active unique.

## Adhkar, Coran et invocations

Le compteur ne progresse qu'après action explicite. Les routines `per_prayer` demandent la prière associée. Les textes d'invocations ont une source saisie par l'utilisateur ; ne pas générer un texte religieux sans vérification. La progression Coran est le dernier point validé, pas un temps de lecture supposé. Un plan de lecture est un repère, jamais un rattrapage imposé. Favori et coche quotidienne sont deux états distincts.

## Calendrier et qibla

Le calendrier Path est hégirien et peut renvoyer deux dates candidates pour un événement prédit. Seule la confirmation utilisateur en retire une. La fenêtre de lecture par défaut est de deux semaines ; ne pas en déduire une limite des données disponibles au cerveau backend. La qibla est un cap depuis le lieu de calcul déclaré, pas une géolocalisation continue.
