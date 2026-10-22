# 11 — Écarts connus et décisions de transmission

Le dépôt contient des documents de dates différentes. Ce dossier ne les modifie
pas pendant que l'autre IA travaille sur le backend. Il en extrait une lecture
opérationnelle et laisse visibles les contradictions.

| Sujet | Écart | Consigne pour générer |
|---|---|---|
| Routes | Doc 59 ancien : `/api/vector/*`, routes parfois TBD ; doc 79/code : `/api/imperium/vector/*` | OpenAPI extrait fait foi pour les URLs/champs |
| Nombre d'écrans | 11 écrans canoniques ; nouvelles routes offres/règles/historique | Sous-vues EXT proposées, pas renumérotation canonique |
| Halo | DS ancien jaune/hésitation ; doc 33 binaire | Vert/rouge ou abstention ; blanc présence, pas de jaune verdict |
| Explications | Doc 57 ancien propose explication du score ; doc 33 interdit le texte live course | Explication après coup ; raison de zone maintenue |
| OCR | Doc 59 upload-only V1, OCR V2 ; décision juin son/capture/OCR critique | Capture API absente aujourd'hui ; besoin cible conservé, aucun faux branchement |
| Priorité signaux | Doc 57 repousse certains événements V2 ; décision juin récurrence × impact | Préserver leur importance V1 cible sans annoncer leur disponibilité |
| Modèle | Phases nommées cold_start/transition/autonomous | Compteurs de collecte ; modèle non entraîné dans le code actuel |
| Scoring actuel | Certaines descriptions de route disent aucun verdict ; service applique rules_only | Exploiter les champs signal/source réels, sans modèle fictif |
| Reco actuelle | Vision flux multi-sources ; code historique revenus par zone | Afficher missing_context, pas de météo/vol/traffic factice |
| Taux horaire | Carte DS prévue ; DTO reco hourly_rate_estimate_cents nul | Ne pas convertir le gain moyen par course en taux horaire |
| Replan | Ancien toast laisse penser automatique | Action explicite après clôture ; réponse = demande, pas plan appliqué |
| Objectif | Cible CA en session ; fatigue/pression interdites au score Vector | Cible visible, aucun mélange entre domaines |
| Capture générique | Knowledge Inbox accepte certains médias | Ne pas l'assimiler à un endpoint Vector/OCR d'offre |
| Offline | Annexe parle header pour tous les drafts | Header uniquement où supporté ; ailleurs version/read-back/conflit |
| Cache | TTL 15 min, stale après 30 min ; intervalle ambigu | Proposition UI « À actualiser » entre 15 et 30 min |
| Destination mode | Ancienne règle évoque 6/jour | Valeur historique de projet, pas limite plateforme certifiée ni compteur actif |
| R7 | Ancien doc parle direction/heading | Code actuel utilise code postal destination et créneau |
| Smart Fuel/HUD tables | Noms vector_* prospectifs | Aucun frontend n'écrit des tables ; données réelles rides_* via API |
| HUD fournisseurs | Annexes supposent des capacités/coûts | À vérifier lors de l'implémentation future, pas garanties de ce kit |

## Autorité

Les demandes utilisateur et règles produit priment. Doc 33 porte la logique
Vector ; doc 57 son détail ML, avec les corrections des décisions explicites
plus récentes. Le code et le contrat exporté définissent ce que l'on peut appeler
aujourd'hui. Une fonction présente dans une annexe n'est pas automatiquement
une fonction activée. Les choix d'interface propres à ce dossier sont identifiés
comme propositions, en particulier les sous-vues EXT et l'intervalle du cache.

## Tables concernées, sans modification

L'intégration observée s'appuie notamment sur `rides_sessions`,
`rides_revenue_entries`, `rides_drop_zones`, `rides_recommendations`,
`rides_offers` et les règles métier du module, avec `imperium_vault_transactions`
pour les écritures financières. Le frontend ne consomme jamais ces tables
directement. Les noms SQL sont un repère de transmission, pas un contrat client.

Ce travail ne modifie aucune de ces tables, aucun handler API, aucune migration,
aucun workflow n8n, ni le périmètre d'activation du MVP.
