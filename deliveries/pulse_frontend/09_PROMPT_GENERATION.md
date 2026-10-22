# Prompt à donner au générateur de frontend

Copier le texte ci-dessous et joindre l'intégralité du dossier décompressé.

---

Construis le frontend de **Pulse**, mon application personnelle Android de sport,
nutrition et suivi santé, utilisable aussi sur tablette. Ce n'est pas un SaaS.
Je suis chauffeur VTC, avec de longues journées et peu d'attention disponible :
les interactions doivent être courtes, simples et explicites. L'objectif est de
suivre le réel et soutenir mes objectifs physiques sans culpabilisation.

Lis d'abord README puis les documents 01 à 10 du kit. Utilise le catalogue
fonctionnel et les quatorze écrans PUL-01 à PUL-14. Les annexes `sources/`
contiennent aussi la vision future ; elles ne prouvent pas la disponibilité d'une
route. Le contrat réel est `contracts/openapi.json`, complété par les notes
sur les uploads et erreurs du document 05.

Le backend commun reste le cerveau : je ne veux aucun calcul stratégique de
santé, aucun choix de modèle IA, aucune écriture PostgreSQL ou appel de fournisseur
direct depuis l'app. Imperium garde l'autorité sur la journée et l'unique mission
active. Pulse affiche, recueille, explique et demande une action backend.

Produis :

1. Une interface complète en français, téléphone et tablette, avec la navigation
   Aujourd'hui / Repas / Sport / Stock / Santé et les sous-vues documentées.
2. Un client API typé, base d'URL configurable, authentification, refresh,
   mapping des erreurs et modèles conformes au contrat joint.
3. Un mode connecté utilisant uniquement les routes existantes et un mode
   démonstration séparé, explicitement marqué, utilisant des données fictives.
4. Les états chargement, vide, hors ligne, synchronisation, conflit, consentement
   absent et fonctionnalité non activée pour chaque parcours.
5. Une file de brouillons avec clé d'idempotence stable par intention et contrôle
   de version ; aucune écriture présentée comme réussie avant confirmation serveur.
6. Les consentements body/pain/medical, les suppressions explicites et la protection
   des photos corporelles strictement locales. Pas de données santé dans les logs.
7. Les écrans programmes/propositions/signaux capables de recevoir un refus
   d'activation du serveur ; jamais d'activation automatique.
8. Des tests des parcours principaux de la recette 08 et un README expliquant
   lancement, configuration, mode démo, tests et limites restantes.

Respecte la palette Pulse et l'accessibilité du document 04. Privilégie le
fonctionnement, puis les animations. Utilise les composants et conventions du
projet frontend d'accueil s'ils existent ; sinon privilégie un frontend Android
natif Kotlin/Jetpack Compose. Si ton environnement ne permet qu'un frontend web,
produis une interface responsive mobile/tablette et indique clairement cette
adaptation, sans prétendre fournir une application Android native.

Ne crée aucune fonctionnalité factice en mode connecté. Les recettes, menus,
courses, batch cooking, analyses médicales automatisées et connexions montre
restent des vues de démonstration ou un backlog tant que leurs API manquent.
Ne calcule pas un score santé, une cible d'eau ou une récupération absents.
Ne transforme pas une estimation de macros en vérité confirmée.
N'utilise pas les anciennes URLs `/api/pulse/...`.

Pour les uploads repas/placard/documents, respecte le corps binaire brut et
les headers documentés ; pas de multipart inventé. Une dictée doit être transcrite
et relue ; ne suppose pas qu'une source `voice` autorise un upload audio.
Une proposition n'est pas une décision appliquée.

Livre le code exécutable, les tests, une liste des écrans réalisés et les limites
d'intégration observées. Ne modifie aucun backend ni flag de production pour
faire fonctionner la démonstration.

---
