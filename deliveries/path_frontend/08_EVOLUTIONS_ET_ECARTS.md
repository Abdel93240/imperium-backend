# 08 — Évolutions et écarts à garder visibles

## Contrats absents ou incomplets

| Sujet | État au snapshot | Décision frontend |
|---|---|---|
| Recherche MAWAQIT, synchronisation réseau manuelle | aucune route dédiée ; mosquées enregistrées et cache consultable | saisie manuelle active ; recherche/sync affichées comme indisponibles si maquette |
| Rappels configurables et notifications de pratique | pas de contrat Path de réglages/planification dédié | aucune fausse bascule « activée » |
| Privacy gate de partage IA par domaine | pas de route Path dédiée | ne pas transmettre de données religieuses à un modèle depuis le client |
| STT/voix Path de bout en bout | pas de route métier Path | saisie manuelle ; préparer uniquement un adaptateur futur |
| Score spirituel Path | absent de `dashboard` | ne pas dessiner un score chiffré inventé |
| Contenu source des adhkar | compteur et suggestions existent, pas de corpus religieux vérifié dans le contrat | ne montrer arabe/traduction que s'ils viennent d'une source validée |
| Qibla temps réel | le backend renvoie un angle ; pas de flux capteur/API propre | boussole locale facultative, provenance affichée |
| Calendrier externe d'observation lunaire | moteur et confirmation manuelle présents, pas de source externe | étiqueter les dates prédites |

## Divergences documentaires à résoudre par le contrat réel

- Le doc 41 ancien donne parfois `/api/path/*` ; le routeur courant expose `/api/imperium/path/*`.
- La logique de calcul documente `Custom/Jafari` comme méthodes possibles, mais `PathSettingsUpdate` accepte `MuslimWorldLeague`, `Karachi`, `Egypt`, `ISNA`. Les madhhabs acceptés sont fournis par la réponse. Le formulaire doit utiliser `supported_methods`/`supported_madhhabs` du serveur.
- `PAT-12 Worship` est décrit dans le doc 41 et la carte 79, moins clairement dans les documents 59/63. Le garder comme regroupement UI des fonctions déjà couvertes par les API.
- Mosquées et adresses ghusl sont top-level dans la carte 79 ; leur gestion est aussi liée depuis Réglages. Autoriser les deux points d'accès à la même vue.
- Le couple `habits/check-ins` Path historique coexiste avec les nouvelles tables spécialisées. Ne pas déduire qu'un check-in vaut une prière, un jeûne ou une sadaqa confirmés.
- Les propositions futures du doc 41 §14-V3 ont été partiellement codées en 2026 : utiliser les routes calendrier effectivement présentes et leurs statuts `predicted/confirmed`.

## Évolutions hors V1

Rappels, recherche réseau MAWAQIT, corpus de contenu religieux sourcé, contribution IA et intégration vocale peuvent être ajoutés lorsque leurs contrats et leurs tests backend existent. La génération actuelle doit isoler ces entrées derrière des capacités détectées, sans inventer de backend parallèle.
