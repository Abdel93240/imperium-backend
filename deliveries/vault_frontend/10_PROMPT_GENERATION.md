# Prompt prêt à copier

Copier le texte ci-dessous et joindre tout le dossier Vault_Frontend_Kit.

---

Construis le frontend complet de **The Vault**, radar financier personnel d'un chauffeur VTC, à partir de ce dossier. Langue française. Cible Android natif Kotlin/Jetpack Compose, Material 3, Galaxy Tab S8 portrait avec sidebar, adaptation téléphone et grande tablette. Les composants et tokens de design sont dans les annexes. Ne crée pas un SaaS.

Lis README puis les documents 01 à 13. Pour les routes et champs, utilise contracts/openapi.json, endpoints.md et forms.md. Les documents 05 et 11 corrigent les matrices historiques. Les fixtures examples sont fictives et validées ; elles ne sont pas un compte réel et ne constituent pas un historique cumulatif.

Implémente la bulle flottante Vault du document 13 : activation locale volontaire depuis VAU-12, permission SYSTEM_ALERT_WINDOW, panneau de saisie gain/dépense partagé avec les formulaires de l'app et même Idempotency-Key. Aucun widget d'écran d'accueil ; aucune dépendance de l'app à la permission overlay. Ce réglage local ne crée pas de PATCH settings backend.

Produis les 12 écrans VAU-01 à VAU-12 et leurs états loading/empty/ready/error/offline/stale/pending/syncing/conflict/disabled. Navigation principale : dashboard, transactions, catégories, réglages. Implémente toutes les fonctions C du catalogue ; prépare des interfaces explicites pour P/F sans inventer d'API ni simuler un succès en mode réel.

Priorité : saisir rapidement une dépense ou un gain, voir les finances réelles, registre et corrections, soldes, échéances, pression explicable, bénéfice hebdomadaire, reçus vérifiés avec sélection Pulse, réglages Path en lecture. + Dépense est l'action principale de l'accueil. Ne produis pas seulement un écran statique.

Crée une couche API typée, repositories, état d'écran, stockage sécurisé de session et brouillons, gestion d'idempotence et cache horodaté. Sépare explicitement une source de données démo et la source réelle configurable. Mode démo : bandeau et zéro écriture réseau réelle. Aucune formule de pression, règle de sadaqa ou stratégie financière dans l'interface. Pas de clé modèle, accès PostgreSQL ou appel n8n direct dans le frontend.

Centimes entiers pour transactions/relevés ; décimaux EUR pour échéances et synthèses. Livre déduit de la catégorie serveur. Bénéfice pro différent du net global. Crypto exclue de la liquidité de pression. Transaction append-only : reverse/correct, jamais DELETE/PATCH du ledger. Déclarer payée utilise mark-paid et ne crée pas une seconde dépense. Pour un ticket, envoie stock_lines explicitement, [] si aucune ligne choisie. Donation/réglages sadaqa appartiennent à Path ; ne les duplique pas.

Authentification et données sensibles selon docs 05/06. Une clé idempotente stable par action supportée ; pas de rejeu aveugle des routes non protégées. Aucun « enregistré » avant réponse positive et statut métier validé. Distingue vrai zéro, valeur absente, relevé, prévu et brouillon.

Réalise les scénarios de recette du document 09. Fournis sources organisées, configuration sans secrets, procédure de lancement/compilation, tests pertinents et liste précise des dépendances non raccordées. Ne change pas le backend, ses contrats ou sa base pour faire passer le frontend. Ne commit rien dans le dépôt backend où une autre IA travaille.

---
