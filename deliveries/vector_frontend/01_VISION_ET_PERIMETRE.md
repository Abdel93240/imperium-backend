# 01 — Vision, périmètre et responsabilités

## Promesse

« Quelle action VTC est la plus rentable et la moins inutile maintenant ? »
Vector aide à choisir une zone, évaluer une proposition de course, réduire les
retours à vide et comprendre la rentabilité réelle du travail. Il est destiné à
un seul chauffeur VTC, souvent occupé et avec peu d'attention disponible.

Ce n'est pas une application de flotte, une place de marché ou un SaaS. Ne pas
ajouter équipes, abonnements, classement de chauffeurs, objectifs gamifiés,
CRM clients ou panneaux d'administration génériques.

## Qui décide

| Élément | Autorité |
|---|---|
| Vector Android | Affichage, formulaires, capteurs autorisés, brouillons, demandes explicites |
| Backend commun | Sessions canoniques, calculs, contrats, validations, règles et idempotence |
| n8n | Orchestration via API ; aucune écriture directe en base depuis le frontend |
| PostgreSQL / pgvector | Données structurées / mémoire sémantique gérées côté backend |
| Imperium | Missions, arbitrages de vie et replanification ; une seule mission active |
| The Vault | Vérité des revenus et dépenses ; pas de second portefeuille Vector |
| L'utilisateur | Acceptation réelle dans Bolt et confirmation des informations |

Une session VTC peut référencer une mission Imperium. La démarrer ne crée pas
une mission autonome et ne clôture pas une mission existante. Le backend accepte
au maximum une session VTC active. Une cible CA est un repère d'affichage ; elle
n'autorise pas Vector à utiliser la pression financière pour noter une course.

## Données permises dans la stratégie VTC

Prix, approche, durée, destination, créneau, zone, historique, trafic, fermetures,
événements, trains, fenêtres aéroport, météo comme signal de demande, majoration,
courses programmées et carburant lorsqu'il affecte l'exécution. Présenter la
source, l'âge et les données manquantes selon le contrat effectivement disponible.

Fatigue, humeur, sommeil, stress, santé, famille, prière et objectif global de
journée ne pilotent pas le score de rentabilité Vector. Imperium peut traiter
ces sujets dans son propre contexte. Une future couche mosquées du HUD est une
information spatiale provenant de The Path, pas une variable du score de course.

## Socle à générer maintenant

Dashboard ; démarrage et session active ; saisie gain/dépense ; emplacement
réservé de capture ; demande/détail/retour de recommandation ; confirmation de
zone de dépose ; bilan et clôture. Ajouter comme sous-vues les offres manuelles,
leur résultat, l'historique, les règles et l'état de collecte déjà exposés par API.
Ces sous-vues `EXT-*` sont des propositions de ce dossier, pas une révision du
catalogue canonique à 11 écrans.

Mode démonstration isolé avec données fictives possible immédiatement. Mode API
réel uniquement avec authentification et réponses réelles. Aucun fallback
silencieux de données fictives après une erreur serveur.

## Limites fermes

Jamais d'auto-clic, d'auto-acceptation, de contournement de protection, de
manipulation de Bolt ni de collecte privée non autorisée. « J'ai accepté » dans
Vector enregistre une décision passée ; cela n'accepte aucune course dans Bolt.
Une capture refusée par Android reste refusée. Aucun score CatBoost ou conseil
stratégique calculé dans l'app. Aucun secret n'est embarqué dans le frontend.

Sources : docs 07, 08, 13, 14, 33, 39, 57 et carte frontend 79.
