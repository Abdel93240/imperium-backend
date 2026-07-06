# CONCEPTION CIBLE DU SCORING / ROUTAGE RESTRUCTURÉ
Date : 2026-07-05. Travail Fable + arbitrage utilisateur + clarifications. STATUT :
conception CIBLE à appliquer QUAND on codera le routage /200 (PAS encore codé — la couche
déterministe doc 52 l'est, le routage attendait le GPU). Restructurer maintenant = zéro
ligne jetée.

## Le défaut du scoring /200 actuel (doc 30 §5)
Il ADDITIONNE des dimensions de nature différente en un seul scalaire /200. Or seuls
CERTAINS critères mesurent la difficulté ; les autres sont des CONTRAINTES ou des FAITS
déterministes. Les fondre crée des routages absurdes.

## STRUCTURE CIBLE EN 3 TEMPS
1. PORTES DURES (100% code, zéro token) — filtrent les modèles ÉLIGIBLES :
   - CONTEXTE : la charge tient-elle dans la fenêtre du modèle ? (le backend connaît le
     COUNT SQL). Une tâche de 50k n'est pas "plus dure", elle est IMPOSSIBLE en local (16k).
     Déjà géré par la règle >20k → store éphémère. Le contexte SORT du score (sinon compté 2x).
   - PRIVACY (confidentialité de la donnée) : donnée intime/médicale → LOCAL ONLY. Porte
     d'éligibilité, JAMAIS un additif de score. (NB : c'est le VRAI privacy, distinct de
     l'importance de la décision — voir ci-dessous.)
   - LATENCE : si une réponse rapide est requise → sélectionne parmi les modèles capables,
     ne RÉDUIT pas la difficulté. SORT du score.
2. SCORE DE DIFFICULTÉ (sur les VRAIS critères de difficulté seulement) — choisit le cran
   dans les modèles restés éligibles. Critères retenus :
   - complexity
   - ambiguity
   - decision_stakes  [= l'importance/gravité de la décision. ANCIEN "data sensitivity",
     MAL NOMMÉ. Ce n'est PAS la confidentialité : c'est l'enjeu. Ex : "quelle voiture
     acheter" = enjeu élevé → gros modèle (plus fin, réunit plus de caractéristiques).
     RESTE dans le score — c'est une vraie raison d'escalader.]
   Renormaliser sur ces critères (la logique /200 survit, sur moins de dimensions).
3. DÉPARTAGE COÛT — seulement quand plusieurs modèles conviennent (le coût n'est PAS une
   entrée du score, c'est l'arbitre final). "cost justification" de l'ancien score = circulaire,
   supprimé (la valeur est déjà dans decision_stakes).

## PERCEPTION = IA, ARITHMÉTIQUE = CODE
Le LLM ne fait JAMAIS l'arithmétique ni ne note 0-10 (non reproductible ; un 6 vs 7 avec
coef ×5 = ±10 pts = change de bande). Le modèle sort des CATÉGORIES en JSON
(complexity: low/medium/high/critical, avec 2-3 exemples ancrés par niveau dans le prompt).
Le BACKEND mappe et calcule. → reproductible + auditable (cohérent "zéro boîte noire").

## VALIDATION DE SORTIE (le vrai filet — plus important que le scoring)
Problème : l'auto-évaluation est BIAISÉE (Qwen jugeant "est-ce trop dur pour Qwen"
se surestime ; documenté, incorrigible par prompt). Solution : on ne fait pas confiance
au routage amont, on VÉRIFIE le résultat aval.
Mécanique : toute exécution LOCALE passe un contrôle déterministe (schéma respecté,
bornes, cohérence). Si ÉCHEC → escalade AUTOMATIQUE d'un cran (Qwen→Sonnet→Opus), on
re-contrôle. Transforme une erreur silencieuse en RETRY. Autorise des seuils AGRESSIFS
vers le local (économies) sans risque de mauvaise réponse silencieuse. Cohérent avec
"les tests sont le verrou, pas la confiance en l'IA".
AMPLEUR RÉELLE (dédramatisé) : PAS un test par requête. 1 validation UNIVERSELLE pour tous
les scorings (format catégoriel toujours identique) + ~1 validation par TYPE DE SORTIE
d'exécution (plan, jugement de chaînage, analyse...). Une poignée, pas des milliers (cf.
"peu de types, toujours les mêmes"). Ajoutées AU FIL DE L'EAU en construisant chaque type,
pas en bloc. C'est du travail qu'on ferait de toute façon (savoir si une sortie est correcte).

## CAS PARTICULIER — LE CONVERSATIONNEL
Une réponse conversationnelle n'a pas de "forme correcte" unique → PAS de validation
déterministe sur le fond. Mais moins risqué : (1) l'HUMAIN est dans la boucle en temps réel
= il est lui-même le validateur (il voit et reformule si Qwen dévie) ; (2) enjeu faible par
tour (on redemande, pas de dégât silencieux).
Garde-fous minimaux quand même : réponse non vide/non tronquée ; respect du privacy gate ;
et surtout — dès que la conversation PRODUIT une action concrète (créer une mission,
modifier un plan, écrire une donnée), CETTE action passe la validation de SON type. La
PAROLE est libre (humain = filet) ; l'ACTION à la frontière est contrôlée (déterministe).

## ROUTES STATIQUES (récurrent) vs SCORING (résidu)
La majorité du trafic = tâches récurrentes connues (phases WR, analyses santé/finance,
scoring courses, CRUD) → TABLE DE ROUTES STATIQUES versionnée, zéro token (comme les routes
forcées actuelles). Le scoring ne traite QUE le résidu inédit (surtout les requêtes ad hoc
du chatbot).

## OPTIMISATIONS — POUR PLUS TARD (V2, quand la contrainte existe)
- Qwen3-4B dédié au routage sur P40 (libère la V100 pour l'exécution, évite la file derrière
  les jobs Phase 3 nocturnes). Justifié SEULEMENT quand le routage sur 32B devient un goulot.
- CatBoost routeur à terme : le log routage→issue devient le dataset (même mouvement que le
  scoring de courses, sub-milliseconde). V2/V3.
- L'incohérence de bornes non tranchée (169 vs 179) devient secondaire : avec un LOG des
  routages et de leurs issues, les seuils se calibrent sur DONNÉES au lieu d'être décrétés.

## LoRA — GARDER LE DATASET LOCAL (règle fondatrice)
Le dataset d'entraînement = le concentré le plus dense de la vie perso (events, validations,
échecs curés+étiquetés). Plus exposant qu'un appel d'inférence ponctuel. → NE PAS l'envoyer
sur GPU cloud loué. Deux issues : (a) QLoRA local sur la config CIBLE (stacking de V100 32Go :
2× = 64 Go, faisable ; Unsloth supporte Volta ; ~1-3 j de calcul pour un réentraînement
trimestriel) ; (b) si cloud un jour pour la vitesse → pseudonymisation systématique avant
upload (events structurés + table de correspondance gardée en local = propre et réversible).
NB config : actuel = 1× V100 32Go + P40 24Go ; cible = stacking de V100 32Go (2×=64, puis
3-4× pour du 70B). La 3090 perd sa justification (le QLoRA devient local).
