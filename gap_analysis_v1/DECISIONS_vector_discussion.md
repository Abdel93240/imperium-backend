# Vector / VTC — Décisions de discussion (acceptation de course + scoring ML)

Date : 2026-06-29
Statut : décisions de fond AVANT gap analysis Vector. Le gap classique a été
ÉCARTÉ pour Vector (voir §6) au profit d'un chantier dédié "matrice des variables".

## 1. CatBoost confirmé (déjà dans doc 57, validé)
- Modèle = CatBoost regression, entraîné sur les courses historiques de l'utilisateur.
- Raison : gère nativement le catégoriel (zones, types), inference <1ms CPU, robuste
  petits jeux de données. Strictement supérieur à XGBoost/LightGBM ici.
- TOURNE SUR CPU. Ne dépend PAS du GPU (V100/P40). Codable sans attendre le matériel.

## 2. Architecture d'exécution = TOUT sur le VPS
- OCR rapide + CatBoost + Valhalla + le "veilleur" → vivent sur le VPS.
- Raison : meilleure connexion réseau, dispo 24/7. L'acceptation de course est
  BLOQUANTE si lente, donc elle va où le réseau est le plus fiable.
- La Tour (GPU) ne porte QUE l'IA "qui a le droit d'être lente" (Whisper, gros
  modèles, OCR précis). Si le réseau maison rame : non bloquant.
- Maillon à MESURER sur le terrain : aller-retour téléphone↔VPS en mobilité.
  (En IDF 5G, attendu instantané sur petits textes. À vérifier en zone faible.)

## 3. Itinéraire = Valhalla LOCAL (jamais l'API réseau en temps réel)
- Calcul d'itinéraire OBLIGATOIRE dans les features (moi→client + client→dépose).
- API Google/TomTom en temps réel = EXCLU pour l'acceptation (latence réseau).
- Valhalla local sur VPS, carte Île-de-France. Le facteur trafic n'est PAS un
  multiplicateur codé en dur : CatBoost l'apprend (cf. Rule R11, durée learned).
- API externes (Google) réservées à l'enrichissement OFFLINE (entraînement), pas
  à la boucle d'acceptation.

## 4. Déclenchement = SON (déjà documenté, confirmé)
- Trigger = son unique de l'appli VTC (fiable même écran éteint).
- son → capture écran → OCR RAPIDE → features → CatBoost → décision.
- 2 OCR distincts : RAPIDE (acceptation, temps réel) vs PRÉCIS (tickets/étiquettes,
  offline, non urgent). Accessibility Service supposé bloqué (FLAG_SECURE) → fallback
  capture+OCR.

## 5. Architecture en 3 temps de la donnée (clarifié cette session)
- TEMPS 1 — CONTEXTE PERMANENT : le "veilleur" récupère EN CONTINU l'état du monde
  (avions posés/terminal, trains, pannes RATP via API IDFM, événements/soirées par
  zone, trafic, position). Prémâché, toujours frais. Vit sur le VPS.
- TEMPS 2 — EXTRACTION COURSE : OCR rapide au moment où ça sonne (prix, lieu, durée
  affichée + constantes connues type délai prise en charge ~2min).
- TEMPS 3 — CROISEMENT : à l'arrivée de l'adresse de dépose → Valhalla (2 itinéraires)
  + zone à rayon ADAPTATIF (2km Paris intra, 3-4km petite couronne, jusqu'à 10km
  province) croisée avec le contexte DÉJÀ prêt → features "retour aéro probable",
  "événement avec retour", "panne = demande accrue" en oui/non instantané.

## 6. DÉCISION MAJEURE — Critère de versionnement = RÉCURRENCE × IMPACT (pas complexité)
- La doc 57 actuelle classe l'événementiel en V2 (§5.6, §15) sur un mauvais critère :
  la DIFFICULTÉ TECHNIQUE. C'est à corriger.
- BON CRITÈRE : une variable va en V1 si elle est RÉCURRENTE et à FORT IMPACT €,
  MÊME si elle est techniquement complexe. "Complexe mais vital = V1 malgré tout."
- Justification économique : un pattern à 2-3×/semaine × +30€ = ~280€/mois = ~3000€/an
  sur UNE variable. Le repousser en V2 = laisser ce revenu sur la table.
- Cas exceptionnels/rares/faible impact = V2/V3 (agrémentation fine, plus tard).

## 7. PIÈGE ML identifié — Variables confondantes (confounding)
- Risque : si CatBoost score une course SANS une variable décisive (ex : événementiel
  pour les courses banlieue nuit/matin), il ne voit pas la CAUSE de la variation du

Le texte fourni dans la demande s'arrête ici. Ajouter la suite quand elle sera
explicitement fournie, sans inventer les décisions manquantes.
