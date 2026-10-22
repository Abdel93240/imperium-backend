# Écarts documentaires et décisions de livraison

Cette livraison ne corrige pas les spécifications historiques ni la roadmap
existante. Elle signale les écarts pour éviter de générer une interface trompeuse.

| Écart observé | Décision pour le frontend |
|---|---|
| Anciennes routes `/api/pulse` | Utiliser seulement les routes du contrat exporté sous `/api/imperium/pulse` |
| Design system indiquant encore plusieurs endpoints TBD | Les routes courantes et schémas font foi pour le branchement |
| Roadmap affichant encore NOT_CODED sur certaines fonctions présentes dans le code | Séparer présence dans le dépôt et activation ; ne pas déduire ON |
| Score santé demandé dans la vision mais `health_score` exclusivement null | Pas de jauge ni score de substitution |
| Objectif d'eau personnalisé futur, `target` nullable | Total réel, état sans objectif |
| Ancien plan « pas de garde-fou dur » pour la douleur | Respecter les red flags et blocages réellement fournis par le backend |
| Spécification des dix procédures plus large que le runner actuel | P1 codée ; les autres restent cible, pas de promesse de traitement |
| Routes d'adaptation historiques accept/reject inexistantes | Utiliser `/proposals/{id}/decision` si activé |
| Photo corporelle mentionnée dans d'anciens exemples de tables | Local uniquement ; schéma actuel refuse tout champ photo |
| Échelles d'énergie différentes selon anciens documents | Conserver le type et les bornes du schéma réel de chaque saisie |
| Idempotence annoncée globalement mais headers absents de certains handlers | Envoyer la clé ; ne pas prétendre à une garantie non implémentée |
| OpenAPI incomplet pour les corps reçus via Request.stream | Compléter avec le contrat d'upload brut du document 05 |
| Orchestration n8n décrite dans la vision, runner présent dans le code récent | Aucun appel orchestration direct du frontend ; uniquement API backend |
| Révision automatique évoquée dans les annexes | Aucun déclenchement cloud ajouté par le frontend |
| API générique de chat/recommandation non exposée | Pas de bouton connecté qui simule une réponse |

## Vérifications à faire au branchement réel

Configurer l'URL et l'appareil de test. Vérifier les migrations et états
d'activation sur cet environnement, sans les modifier implicitement. Exécuter la
recette des consentements, OCR, jeûne, propositions et conflits. Vérifier la
configuration réseau/CORS si la cible retenue est web, et les autorisations
Android si la cible est native. Le kit n'affirme pas que ces dépendances sont actives.

## Traçabilité

Le manifeste indique l'instant d'export, le commit de référence, l'état modifié
des fichiers sources sélectionnés et leurs empreintes. Le contrat est extrait
du checkout courant, qui peut contenir des modifications non commitées.
Les données d'exemple sont synthétiques ; aucune base utilisateur n'a été exportée.
