# DÉCISION — Démarrage de journée (contrat canonique)
Date : 2026-09-08. Source : audit read-only Opus 5 + arbitrage utilisateur. Fait foi sur les versions divergentes des docs 28, 43, 52 et de la spec Daily.

## Déclencheur
Clic explicite "Démarrer la journée". Pas de démarrage automatique (heure, réveil).

## Avant démarrage
- Mission actuelle : état "Journée non démarrée". Ne pas afficher une mission restée active de la journée précédente.
- Programme du jour : masqué jusqu'au démarrage.

## Au clic
1. Check-in : UNE seule question, le ressenti subjectif ("Comment tu te sens aujourd'hui ?", échelle courte). Rien d'autre n'est demandé.
2. Sélection déterministe dans le plan courant (cible < 500 ms).
3. Vérification de fraîcheur déterministe : calendrier modifié depuis la génération, missions non faites de la journée précédente, contraintes récentes.
4. Si conflit ou infaisabilité : IA locale (Qwen3.6-27B, via le scoring). Cloud uniquement pour une régénération exceptionnelle validée par l'utilisateur.
5. Front : "Démarrage…" (quasi instantané) ; "Préparation de votre journée…" uniquement si le repli IA se déclenche. Anti double-clic. Délai max et reprise après échec : à définir.

## Énergie = deux axes
- Objectif (déterministe, automatique) : sommeil (montre connectée), nutrition / caféine / hydratation déclarées dans Pulse, charge de la journée précédente. Estimation avec marge, pas une mesure exacte.
- Subjectif (check-in) : ressenti déclaré. On peut avoir le corps prêt et le moral à plat, ou l'inverse.
- Combinaison : capacité de charge retenue = la plus basse des deux axes.
- L'écart entre énergie calculée et énergie ressentie est enregistré : signal de calibrage de l'algorithme.

## Principe de résolution (transverse à tout l'écosystème)
- L'IA ne répond jamais "impossible" ni "trop dangereux, arrête". Elle cherche parmi les chemins possibles celui qui atteint le maximum de l'objectif (viser ≥ 80 %) avec un danger minimal.
- Conduite VTC avec corps fatigué : la contrainte porte sur la FORME des blocs (durée maximale de conduite continue, fonction de l'énergie objective), jamais sur l'arrêt du travail. La pression financière reste l'objectif à atteindre.
- Méthode : placer des blocs courts sur les heures à plus fort rendement (scoring VTC zones/heures), sommeil ou siestes dans les creux. Exemple type : sommeil → 2 h en pointe → sommeil pendant le creux → 2 h en pointe.
- Si aucun chemin n'atteint l'objectif : bannière rouge + meilleur plan partiel + écart chiffré (ex : "320 € sur 400 € atteignables, voici les options pour les 80 € restants"). L'utilisateur arbitre. Jamais de blocage sec.
- Mise en œuvre : interdiction explicite du refus dans le prompt système du planificateur ; en validation de sortie, un plan de type "refus sans alternative" est une sortie INVALIDE → rejet et escalade automatique d'un cran.
- But : le travail de recherche de solution est fait par l'écosystème, pas par un utilisateur épuisé qui rumine avec un cerveau au ralenti.

## Douleurs et santé en cours de journée
Pas de question au check-in. Déclaration à tout moment via le chatbot → health.entry.logged → l'IA propose un réajustement en montrant le programme restant, ou demande si l'utilisateur s'en sent capable → si accepté : planning.daily_plan.replanned {reason: pain}, relié par causation_id. Jamais de réorganisation sans accord.

## Journée opérationnelle
Bornée démarrage → clôture, peut dépasser minuit (jusqu'à ~36 h). "Aujourd'hui" ne doit plus être calculé par date civile (bug relevé : daily_plans.py:134, core/dates.py:8).

## Modèles
- Local : Qwen3.6-27B-Q6_K (doc 30 fait foi). Qwen 2.5 7B (AGENTS.md, ère CPU Hostinger) : obsolète, à retirer. Qwen3-32B : abandonné.
- Cloud frontière : Claude Opus 5.5 (ID API claude-opus-5-5). L'appel réel utilise l'alias "opus", qui pointe toujours sur le dernier Opus.

## À faire côté code
Raccorder le bouton ; état "journée non démarrée" ; masquage du programme ; check-in ressenti ; vérification de fraîcheur ; journée opérationnelle au lieu de la date civile ; payload replanned avec version et reason (doc 77) ; principe de résolution dans le prompt du planificateur + validation de sortie anti-refus.
