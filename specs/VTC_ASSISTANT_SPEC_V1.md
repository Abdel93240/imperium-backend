# SPEC — VTC RIDE ASSISTANT « VECTOR » V1

> **Livrable d'implémentation one-pass, BI-CIBLE.** Prompt d'exécution destiné à Claude Code
> (Fable 5). Deux cibles : **Cible A** = l'application Android Vector (repo `vtc-companion-app`,
> GitHub Abd93240) ; **Cible B** = le backend Tower (`/opt/imperium-backend`). Il implémente
> l'assistant d'acceptation de course : déclencheur audio, capture, OCR embarqué, features en
> caches poussés, estimateur de trajet local, CatBoost ONNX embarqué, halo consultatif,
> professeur fantôme Google/TomTom, réentraînement nocturne verrouillé, annexes majoration et
> repositionnement, protocole du test fantôme avec seuils gravés.
> Numérotation : nouveau doc au prochain numéro libre de `docs_master/`.
> Cette spec fait système avec les trois précédentes (Pulse, WR Continuous Engine, Daily
> Orchestrator) : docket, usine W1/W4, table events canonique post-E3, paramètres versionnés.

---

## 0. MODE D'EMPLOI POUR L'EXÉCUTEUR (à lire en premier)

**Ton rôle** : implémenter l'intégralité de cette spec en une passe, ordre §10, tests §9 en
verrous. Deux dépôts, deux sections d'exécution, un seul contrat d'interface (§2.3).

**Étape 0 obligatoire — AUDIT AVANT TOUTE ÉCRITURE.** Produire `VTC_MAPPING.md` (déposé dans
les deux repos) répondant à :
1. État réel de `vtc-companion-app` : langage, structure, écrans existants (données mock),
   permissions déjà déclarées, état de la CI (GitHub Actions APK était en attente).
2. Backend : tables VTC existantes (courses réalisées, sessions VTC — ~800 courses/mois
   d'historique évoquées : où vivent-elles, quelles colonnes : prix, durées, horodatages,
   lieux ?). Sans cet historique localisé, la matrice de base (§3.5) et les labels de zones
   (§4.5) n'ont pas de source — STOP et signaler si introuvable.
3. Passes précédentes : `wr_docket_items`/usine (spec WR) présentes ? Table de paramètres
   versionnés présente ? Table events canonique post-E3 identifiée ? Adapter les branchements
   §4.8/§7 en conséquence (si l'usine n'est pas posée, livrer les items de dérive dans une
   table tampon + TODO documenté, ne pas bloquer).
4. La plateforme VTC principale de l'utilisateur (template d'écran d'offre §3.3) : demander à
   l'utilisateur UNE capture d'exemple d'écran d'offre par plateforme utilisée avant d'écrire
   les templates. Ne jamais inventer la disposition d'un écran.
5. Consigner créer/étendre/couvert pour chaque table du §5.

**Contraintes globales non négociables** :
- Anglais en base/API/code, français en libellés utilisateur.
- **ZÉRO LLM dans ce système.** C'est le membre 100 % déterministe + ML classique de la
  famille. Aucun slot, aucune exception.
- **Consultatif strict** : le système ne touche JAMAIS à l'application VTC — aucune injection
  de tap, aucune auto-acceptation, aucun accessibility service qui agit. Il affiche un halo.
- **Chemin critique 100 % embarqué** : de la sonnerie au halo, zéro appel réseau. Les caches
  sont poussés en avance, le modèle est sur la tablette.
- **Abstention honnête** : donnée douteuse (OCR partiel sur champ requis, cache périmé) →
  halo reste blanc. Jamais une couleur confiante sur du douteux.
- **Micro on-device only** : le flux audio du déclencheur est traité en mémoire (tampon
  glissant de quelques secondes), jamais enregistré, jamais transmis. Gravé, testé (§9.2).
- Apprentissage : issues depuis les seules courses ACCEPTÉES (règle anti-pollution de
  l'utilisateur) ; features loggées pour TOUTES les offres ; acceptations contre-halo
  marquées `exploration`.
- Feature flags : `vtc_assistant_enabled` + `vtc_assistant_mode` ∈ {off, shadow, advisory}.
  En `shadow`, tout le pipeline tourne et logge, le halo reste blanc.
- Aucune donnée personnelle en dur ; migrations réversibles idempotentes.

**Definition of Done** : les deux cibles compilent et passent leurs tests §9 + budget de
latence prouvé sur fixtures (§9.1) + mode shadow end-to-end (sonnerie simulée → capture
fixture → OCR → score → log, halo blanc) + VTC_MAPPING.md + patch doc 77 (events §7) +
CI GitHub Actions APK fonctionnelle si elle ne l'était pas.

---

## 1. CONTEXTE ET PRINCIPES

Le pool des plateformes VTC parisiennes propose chaque course à ~15 chauffeurs simultanément :
la fenêtre réelle sur les bonnes courses est de 2-3 secondes. Le système initialement décrit
(capture → 4G → OCR P40 → appel Google → CatBoost → 4G → halo) tient la médiane (~1,2 s) et
meurt en p95 (3-5 s) — et la latence échoue en corrélation inverse avec la valeur de la
course. D'où l'inversion gravée dans cette session :

1. **La tablette décide, la Tower enseigne.** OCR ML Kit on-device, CatBoost ONNX on-device,
   features depuis caches poussés, estimateur de trajet local. Budget : sonnerie → halo
   ≤ 900 ms p95, fonctionnel dans un parking souterrain.
2. **Google/TomTom sort du chemin critique et devient professeur** : appel fantôme asynchrone
   par offre — s'il revient dans la fenêtre il AFFINE (upgrade only : il colore un blanc
   d'incertitude, ne rétrograde jamais un halo affiché) ; sinon il note la copie et calibre.
3. **Le juge du test fantôme est le réel**, pas l'un des deux estimateurs (annexe A, §6).
4. **La rentabilité est le €/h du cycle complet** : prix ÷ (approche + attente client apprise
   + course + temps mort attendu dans la zone de dépose). Une course qui dépose dans un désert
   n'a pas le €/h de son ticket.
5. **Le seuil est un quantile de la distribution des OFFRES de la période**, pas la moyenne
   des acceptées (biaisée haut par construction).
6. **Les caches battent les appels** : tout le contexte (trafic, transports, aéroports,
   événements, travaux, seuils, scores de zones) est poussé périodiquement en quelques ko.
7. **Le récurrent vit dans la matrice, l'exceptionnel dans le multiplicateur** : la matrice
   cellule×heure×type-de-jour encode le périph du mardi 8h30 ; le flux 5 min encode l'accident
   de l'A86 — écart à l'attendu DU CRÉNEAU, jamais à la vitesse « normale » (pas de double
   comptage).
8. **La majoration s'anticipe, elle ne se constate pas** : quand la couleur s'affiche, la
   fenêtre est morte. D'où le prédicteur cause→surge et ses protocoles de capture (§3.9, §4.6),
   négatifs compris (les causes qui n'ont RIEN produit).
9. **Un seul modèle de zones, deux consommateurs** : pénalité de dépose du scoreur ET bouton
   « Où je vais » (§4.5).
10. **Réentraînement nocturne sous verrou de backtest** : jamais de déploiement d'un modèle
    qui fait moins bien que l'actuel sur les 14 derniers jours ; dérive de calibration →
    docket WR.

---

## 2. ARCHITECTURE

### 2.1 Vue d'ensemble
```
┌─ CIBLE A — TABLETTE (Vector) ─────────────────────────────────────────────┐
│ Détecteur audio (empreinte sonnerie, on-device) ──► Capture (+2e à 300ms) │
│   ──► OCR ML Kit (templates par plateforme) ──► Assembleur de features    │
│   (caches locaux + GPS + horloge) ──► Estimateur trajet local             │
│   (matrice H3 + multiplicateurs live) ──► CatBoost ONNX ──► HALO          │
│   blanc=abstention/attente · vert=conseillé · rouge=déconseillé           │
│ Log intégral des offres (Room) ──► sync asynchrone ──► Tower              │
│ Boutons : capture surge manuelle · « Où je vais » · session               │
└──────────────▲───────────────────────────────┬────────────────────────────┘
    caches poussés (5 min, qq ko)      logs offres/captures (async)
               │                               ▼
┌─ CIBLE B — TOWER ─────────────────────────────────────────────────────────┐
│ Builders de caches (trafic, transports, aéroports+bagages, événements,    │
│ travaux, seuils par période, scores de zones) · Fantôme Google/TomTom     │
│ (async/offre, recyclé en multiplicateurs) · Datasets & entraînement       │
│ nocturne CatBoost + verrou backtest + export ONNX versionné · Modèle de   │
│ zones unifié · Prédicteur cause→surge · Contre-lecture OCR (P40) ·        │
│ Dérive → docket WR (usine W4/W5)                                          │
└────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Ce qui est mort et enterré
Plus d'OCR sur P40 dans le chemin critique (elle garde la contre-lecture nocturne et
l'entraînement). Plus d'appel Google bloquant. Plus d'aller-retour Tailscale entre la sonnerie
et le halo. Le seul module tablette autorisé à parler au réseau en direct est « Où je vais »
(§3.10) — l'utilisateur est à l'arrêt.

### 2.3 Contrat d'interface A↔B (fichiers JSON versionnés `schema_version`)
- **Descente (Tower→tablette)** : `context_cache.json` (5 min : multiplicateurs trafic par
  cellule H3, perturbations transports, arrivées aéroports + tampon bagages, seuils de période,
  scores de zones, TTL par section) ; `static_cache.json` (hebdo : événements, travaux) ;
  `model_bundle/` (CatBoost ONNX + matrice de base + version + hash).
- **Montée (tablette→Tower, asynchrone, batché, idempotent)** : `offers_log`, `surge_captures`,
  `reposition_log`, `session_markers`, `stage_timings`.
- Transport : Tailscale, reprise sur coupure, aucun payload > 1 Mo hors images de capture
  (uploadées compressées, en Wi-Fi ou fin de session par défaut, paramétrable).

---

## 3. CIBLE A — APPLICATION ANDROID (Vector)

### 3.1 Déclencheurs
- **Primaire — empreinte audio** : service foreground actif uniquement quand
  `assistant actif ET session VTC en cours`. Tampon audio glissant en RAM (≤ 3 s), corrélation
  croisée contre l'empreinte de la sonnerie d'offre. Écran de calibration : l'utilisateur fait
  sonner 3 offres (ou rejoue le son), l'app enregistre l'empreinte par plateforme. Seuil de
  détection paramétré, latence cible ≤ 250 ms. Gravé : flux jamais persisté, jamais transmis.
- **Secondaire — test notification (unique, instrumenté)** : `NotificationListenerService` en
  écoute PASSIVE 2 semaines : logger (horodatage, plateforme, texte disponible o/n). Deux
  issues : texte exploitable → double déclencheur (le premier arrivé lance la capture) ; texte
  vide/absent (FLAG_SECURE soupçonné) → on garde uniquement l'horodatage s'il précède le son
  (avance gratuite), sinon suppression du service. Décision consignée en paramètre.
- **Double capture** : capture immédiate + seconde à +300 ms si l'OCR de la première rate un
  champ requis. Deux images coûtent rien, une offre ratée coûte une course.

### 3.2 Capture
`MediaProjection` en session persistante (autorisation demandée à l'activation de
l'assistant, foreground service `mediaProjection`). Halo par overlay
(`SYSTEM_ALERT_WINDOW`) — permission demandée à l'activation avec écran d'explication.
Vérifier à l'audit les contraintes de la version Android de la tablette (rétention de la
session MediaProjection, service audio + projection simultanés). La capture est recadrée à la
zone d'offre du template avant OCR (moins de pixels = plus vite).

### 3.3 OCR embarqué & templates
ML Kit Text Recognition v2, on-device. **Registre de templates par plateforme**
(`vtc_capture_templates`, §5) : zones relatives (prix, ETA/distance d'approche, adresse ou
zone de prise en charge, destination, multiplicateur de majoration s'il figure), regex de
validation par champ, `min_confidence` par champ, version datée — les plateformes changent
leurs UI sans prévenir, le template est de la donnée, pas du code. Champs REQUIS pour scorer :
prix, approche (temps ou distance), destination. Champ requis manquant après double capture →
**abstention** (halo blanc) + log `abstained_reason`. Benchmark d'acceptation gravé : ≥ 98 %
d'extraction correcte des champs requis sur 50 captures fixtures par plateforme (§9.3), sinon
le template retourne en atelier.

### 3.4 Assembleur de features (code pur, ≤ 50 ms)
Sources : OCR + `context_cache.json` + `static_cache.json` + GPS + horloge + état session
(heure de début, gains cumulés, fin prévue). Vérification de fraîcheur par section (TTL
dépassé → feature marquée stale). Stale sur une section CRITIQUE (trafic, seuils) →
abstention ; stale sur une section secondaire (événements) → feature neutralisée + flag.
Whitelist stricte : aucune feature ne peut venir d'un appel réseau au moment T.

### 3.5 Estimateur de trajet local (code pur, ≤ 50 ms)
```
temps(A→B) = Σ segments [ base_matrix(cellule_H3, heure, type_jour) ] × mult_live(corridor)
```
- **Matrice de base** : cellules H3 (résolution P:h3_res, défaut 8), vitesses/temps attendus
  par (cellule, tranche horaire, type de jour {ouvré, samedi, dimanche/férié, vacances
  scolaires}), calibrée par la Tower sur l'historique réalisé (~800 courses/mois) + un fond
  cartographique OSM pour les cellules jamais visitées (fallback marqué).
- **Multiplicateurs live** : écart courant à l'attendu DU CRÉNEAU, par cellule/corridor,
  depuis le cache 5 min. Jamais d'écart à la vitesse libre (double comptage interdit, testé).
- Cheminement : pas de routage complet embarqué en V1 — approximation par corridor de
  cellules H3 entre A et B (ligne brisée élargie), suffisante pour un verdict binaire à seuil.
  Le fantôme mesure l'erreur réelle ; si le test (§6) montre que la granularité route change
  les verdicts, GraphHopper offline devient la V1.1 (hors périmètre, documenté).

### 3.6 Scoreur embarqué (≤ 10 ms)
CatBoost exporté ONNX, onnxruntime-android, CPU. **Le modèle régresse le €/h du cycle
complet** ; le verdict est du code :
```
eph_estime = prix / (approche + attente_client(heure) + course + temps_mort(zone_dépose, heure))
verdict    = eph_estime ≥ seuil_période (quantile poussé dans le cache)
marge      = (eph_estime − seuil) / seuil    # loggée, sert au test fantôme et à l'UX
```
`attente_client(heure)` et `temps_mort(zone,heure)` viennent du modèle de zones (§4.5) via le
cache. Les cas proches du seuil restent COLORÉS (le métier du halo est de trancher) ; la bande
d'indifférence P:indifference_band (10 %) ne sert qu'à l'évaluation (§6). L'abstention est
réservée aux données douteuses, jamais aux cas serrés.

### 3.7 Halo (overlay)
États : blanc (assistant actif / abstention), vert (conseillé), rouge (déconseillé). Règle
d'affinage : si le fantôme Google revient DANS la fenêtre (rare), il peut colorer un blanc
d'abstention ou confirmer — **jamais rétrograder une couleur affichée** (zéro clignotement).
Optionnel paramétrable : liseré d'intensité proportionnel à |marge| (désactivé par défaut —
l'UX gravée est binaire et glançable).

### 3.8 Log intégral des offres (Room, puis sync)
UNE ligne par offre sonnée, acceptée ou non : horodatage, plateforme, template_version,
champs OCR + confiances, snapshot features (jsonb), eph_estime, seuil, marge, verdict,
halo_affiché, latences par étage (trigger, capture, ocr, features, trajet, score, rendu),
abstained_reason?, action_utilisateur si déductible (course démarrée dans les 90 s = acceptée,
sinon inconnue/refusée), `exploration=true` si acceptée sous halo rouge (ou refusée sous
vert). Ce log est LA matière première de tout l'apprentissage — sa complétude est testée.

### 3.9 Flux de capture majoration (annexe B, côté app)
- **Manuel** : bouton capture surge → l'utilisateur cadre la carte de chaleur plein-région
  (zoom imposé rappelé à l'écran) → upload différé. Une capture large = ~100 observations de
  zones (colorées = positifs, vides = négatifs valides à cet instant).
- **Déclenché par cause** : la Tower détecte une cause candidate (perturbation transport,
  accident majeur, événement qui commence) → notification « si tu es à l'arrêt : une capture »
  — surtout si la carte est vide (négatif = or).
- **Battement de cœur** : optionnel (P:surge_heartbeat, défaut 60 min), une sollicitation par
  heure de session, à l'arrêt.
- **Garde-fou absolu** : toute sollicitation et tout bouton de capture sont inertes si
  vitesse GPS > P:capture_speed_max (5 km/h). Jamais de capture en roulant.

### 3.10 Bouton « Où je vais » (repositionnement)
Visible quand aucune course active. Appui → requête Tower (l'utilisateur est à l'arrêt, le
réseau est acceptable ici) : position + contexte → **3 zones classées par €/h NET depuis la
position** = gains attendus heure suivante ÷ (trajet pour y aller + attente attendue sur
place). Réponse affichée : zone, temps de trajet, une ligne de pourquoi (générée par template
déterministe depuis les features : « CDG : 14 vols posés 22h-23h », « surge prédit ×1,8 gare
de Lyon »), validité ~20 min sans churn si immobile. Pondération fin de session : dans la
dernière P:endgame_window (90 min), bonus aux zones vers le point de retour. Hors-ligne →
fallback : derniers scores de zones du cache, marqué « estimation ». Log passif uniquement :
zone recommandée, zone effectivement prise (GPS, cellule tenue ≥ 10 min), €/h de l'heure
suivante — zéro friction, pas de raison demandée ; choix hors-recommandation = exploration.

### 3.11 Sync & modèles
WorkManager : montée des logs (batch, idempotent par uuid), descente des caches (5 min en
session, sinon horaire), descente des bundles modèle avec vérification de hash + activation
atomique (hot-swap entre deux offres, jamais pendant un scoring). Chaque scoring logge la
version du modèle et des caches utilisés (reproductibilité).

---

## 4. CIBLE B — BACKEND TOWER

### 4.1 Builders de caches (crons, code pur)
- `traffic_multipliers` (5 min en session VTC active, sinon dormant) : sources combinées du
  moins cher au plus riche — données publiques IdF (Sytadin/DiRIF, comptages parisiens — vérifier
  disponibilité/format à l'implémentation), API de flux TomTom Traffic si souscrite (paramètre),
  et **recyclage des fantômes** (§4.2 : ratio durée_trafic/durée_typique de chaque réponse
  Directions = multiplicateur du corridor traversé, gratuit). Sortie : multiplicateur par
  cellule H3 = vitesse_courante / vitesse_attendue_du_créneau.
- `transports` (5 min en session) : perturbations RATP/SNCF — feature de DEMANDE pour CatBoost
  et cause candidate pour le surge, PAS une feature de temps de trajet (deux tuyaux, nommés).
- `airports` (60 min en session) : arrivées CDG/Orly + tampon bagages P:baggage_buffer_min (30)
  ajouté au temps d'atterrissage.
- `events` + `roadworks` (hebdo) ; `period_thresholds` (nocturne, §4.3) ; `zone_scores`
  (15 min en session, §4.5).

### 4.2 Fantôme Google/TomTom (asynchrone, par offre)
À réception de chaque ligne d'offre : appel Directions (A→pickup, pickup→dest) horodaté
précisément (envoi, réception). Usages : (1) juge de latence — la réponse serait-elle arrivée
dans la fenêtre ? ; (2) calibration — erreur locale vs Google vs RÉALISÉ ; (3) recyclage en
multiplicateurs (§4.1) ; (4) affinage temps réel best-effort vers la tablette si la réponse
revient vite (upgrade only, §3.7). Budget API plafonné P:ghost_daily_cap, échantillonnage si
dépassé (priorité aux offres proches du seuil).

### 4.3 Datasets & seuils (nocturne)
- `vtc_offers` consolidées (montées de la tablette) ; issues jointes : pour les acceptées,
  temps réels et prix réel depuis l'historique de courses → **eph_realise du cycle complet**
  (jusqu'à l'offre suivante acceptée ou fin de session : le temps mort de dépose est DANS le
  réalisé).
- `period_thresholds` : quantile P:threshold_quantile (défaut 0,50) de eph_estime des OFFRES
  loggées par sceau de période (tranche horaire × type de jour × vacances scolaires),
  fenêtre glissante P:threshold_window_days (28), lissage minimal d'effectif (sceau < 30
  offres → repli sur le sceau parent). Poussé dans le cache.
- Poids d'entraînement : `exploration=true` → sample_weight × P:exploration_weight (3.0).

### 4.4 Entraînement nocturne sous verrou
CatBoost régression sur eph_realise (features = snapshot d'offre), fenêtre glissante
P:train_window_days (120). **Verrou de backtest** : évaluation du candidat ET du modèle en
production sur les 14 derniers jours (exclus de l'entraînement du candidat) — métriques :
justesse de décision (le verdict aurait-il correspondu à eph_realise ≥ seuil ?) et MAE.
Candidat ≤ production sur la justesse → PAS de déploiement, log + compteur. Déploiement :
export ONNX, `vtc_model_versions` (date, fenêtres, métriques, hash), push bundle. Rollback =
re-push de la version précédente (une commande).

### 4.5 Modèle de zones unifié (deux consommateurs)
Dataset rétroactif depuis l'historique de sessions : pour chaque (cellule H3 tenue, heure,
contexte du moment {jour, vacances, événements actifs, perturbations, surge connu}) →
cibles : **€/h de l'heure suivante** et **temps d'attente avant prochaine course**. Des mois
de sessions 12 h = milliers d'échantillons gratuits. Deux régresseurs CatBoost sur le même
dataset. Limite honnête documentée : couverture censurée aux zones fréquentées — amorçage par
priors métier (aéroports selon arrivées, gares, événements) + sortie du prédicteur surge en
entrée + fond neutre ailleurs, marqué `low_coverage`. Consommateurs : (1) `temps_mort(zone,h)`
et `attente_client(h)` du scoreur embarqué (via cache) ; (2) le bouton « Où je vais » :
score_net(zone) = eph_next_hour(zone) / (trajet(position→zone) + attente(zone)) → top 3.

### 4.6 Prédicteur cause→surge (annexe B, côté Tower)
- Ingestion des captures carte : extraction couleur → intensité par cellule H3 (pipeline
  déterministe, zoom imposé) → `vtc_surge_observations` (cellule, ts, intensité, capture_ref) —
  les cellules vides de la capture sont écrites en intensité 0 (les négatifs SONT des données).
- Jointure aux causes actives au moment T (transports, accidents, événements, heure, jour).
- Calibration couleur→valeur : offres sonnées DANS une cellule colorée (multiplicateur OCR
  connu) → table de correspondance intensité→multiplicateur.
- Modèle : gradient boosting classif/régression (cause, contexte, cellule) → surge attendu à
  +15/+30 min. Consommateurs : feature CatBoost (valeur de course), entrée du modèle de zones,
  notifications de capture ciblées (§3.9). Réponse à la question gravée « à quel point la
  majoration joue sur le €/h » : rapport mensuel automatique = importance de la feature +
  dépendance partielle du CatBoost principal, en €/h réalisés — item docket informatif.
- V2 explicitement hors périmètre : seuil d'acceptation dynamique piloté par le surge de la
  zone courante (coût d'opportunité temps réel).

### 4.7 Contre-lecture OCR (P40, nocturne)
Échantillon P:ocr_audit_pct (20 %) des captures montées (+100 % des abstentions pour champ
manquant) re-OCRisées sur la P40 (pipeline Paddle existant). Désaccord champ à champ vs
l'extraction embarquée → items `template_fix` groupés par plateforme/version ; taux d'accord
par template dans les métriques. C'est l'audit décroissant appliqué à un capteur.

### 4.8 Dérive → docket WR
Jobs hebdo (branchés usine W4/W5 si présente, sinon table tampon) : calibration prédite vs
réalisée (MAE glissante, biais signé — suspicion de changement d'algo plateforme si rupture),
part d'abstentions, taux d'accord OCR, taux d'overrides exploration, couverture du modèle de
zones. Chaque dérive au-delà de sa bande → item docket, jamais d'auto-correction.

---

## 5. SCHÉMA DE DONNÉES (Tower ; la tablette a ses miroirs Room minimaux)

```sql
CREATE TABLE vtc_offers (
  id uuid PRIMARY KEY,                    -- généré tablette (idempotence sync)
  ts timestamptz NOT NULL, platform text NOT NULL, template_version int NOT NULL,
  ocr_fields jsonb NOT NULL, ocr_confidences jsonb NOT NULL,
  features jsonb NOT NULL,                -- snapshot complet au scoring
  eph_estimated numeric, threshold numeric, margin numeric,
  verdict text NOT NULL,                  -- green|red|abstain
  abstained_reason text,
  halo_shown text NOT NULL,               -- ce qui a été réellement affiché (mode shadow: white)
  stage_timings jsonb NOT NULL,           -- ms par étage
  model_version text NOT NULL, cache_versions jsonb NOT NULL,
  user_action text,                       -- accepted|not_accepted|unknown (déduit, 90 s)
  exploration bool NOT NULL DEFAULT false,
  ride_ref uuid,                          -- jointure vers la course réalisée si acceptée
  eph_realized numeric                    -- rempli au nocturne, cycle complet
);

CREATE TABLE vtc_ghost_scores (
  id uuid PRIMARY KEY, offer_id uuid NOT NULL REFERENCES vtc_offers(id),
  provider text NOT NULL, sent_at timestamptz, received_at timestamptz,
  eta_pickup_s int, eta_ride_s int, typical_ride_s int,
  would_have_arrived_in_window bool, eph_ghost numeric, verdict_ghost text
);

CREATE TABLE vtc_capture_templates (
  id uuid PRIMARY KEY, platform text NOT NULL, version int NOT NULL,
  zones jsonb NOT NULL, field_rules jsonb NOT NULL,   -- regex + min_confidence par champ
  required_fields text[] NOT NULL, active bool NOT NULL,
  fixture_pass_rate numeric,              -- score du benchmark §3.3 (≥ 0.98 exigé)
  UNIQUE (platform, version)
);

CREATE TABLE vtc_model_versions (
  id uuid PRIMARY KEY, model_kind text NOT NULL,  -- acceptance|zone_eph|zone_wait|surge
  trained_at timestamptz, train_window jsonb, metrics jsonb NOT NULL,
  backtest jsonb NOT NULL, deployed bool NOT NULL, onnx_hash text, notes text
);

CREATE TABLE vtc_surge_captures (
  id uuid PRIMARY KEY, ts timestamptz, kind text NOT NULL,  -- manual|cause_triggered|heartbeat
  cause_ref text, image_ref text, processed bool NOT NULL DEFAULT false
);
CREATE TABLE vtc_surge_observations (
  id uuid PRIMARY KEY, capture_id uuid REFERENCES vtc_surge_captures(id),
  h3_cell text NOT NULL, ts timestamptz NOT NULL, intensity numeric NOT NULL,  -- 0 = négatif valide
  multiplier_calibrated numeric
);

CREATE TABLE vtc_reposition_log (
  id uuid PRIMARY KEY, ts timestamptz, position_cell text,
  recommendations jsonb NOT NULL,          -- top3 servi (zones, scores, raisons)
  taken_cell text, taken_detected_at timestamptz,
  eph_next_hour numeric, followed bool
);

CREATE TABLE vtc_base_matrix (
  h3_cell text, hour_band text, day_type text,
  speed_kmh numeric, source text,          -- history|osm_fallback
  updated_at timestamptz, PRIMARY KEY (h3_cell, hour_band, day_type)
);
-- + tables tampon dérive si l'usine WR est absente (audit §0.3).
```

---

## 6. ANNEXE A — PROTOCOLE DU TEST FANTÔME (seuils gravés AVANT le test)

**Objet** : trancher le seul désaccord ouvert — l'estimateur local suffit-il dans le chemin
critique, ou la granularité route de Google change-t-elle les verdicts ?

**Dispositif** : pendant la phase shadow puis les premières semaines advisory, le local pilote
(il est toujours dans la fenêtre), le fantôme score chaque offre en arrière-plan. **Le juge est
le réalisé** : sur les courses acceptées, |estimation locale − réel| vs |estimation Google −
réel|, temps d'approche et de course séparés.

**Durée** : 2 semaines minimum, prolongées à 4 si verdict ambigu OU période atypique (un test
en vacances scolaires ne vaut pas pour novembre — le sceau de période est loggé).

**Trois métriques, gravées** :
1. **Taux de bascule de décision** (LA métrique) : part des offres HORS bande d'indifférence
   (|marge| ≥ P:indifference_band, 10 %) où local et Google donnent des verdicts opposés.
2. **Erreur vs réalisé** : MAE et biais signé des deux estimateurs, par type de segment
   (intra-Paris / corridor autoroutier / mixte).
3. **Disponibilité dans la fenêtre** : part des réponses Google reçues < P:pool_window_s (2,5 s)
   après la sonnerie. « Acceptée en une seconde alors que Google ne serait pas rentré » devient
   un pourcentage.

**Règles de décision (défauts à valider avant lancement, puis intangibles pendant le test)** :
- bascule < 3 % ET erreur locale ≤ 1,25 × erreur Google → **local seul** dans le chemin
  critique, Google sort définitivement (reste professeur §4.2). 
- bascule > 8 % → Google réintègre le chemin critique en mode course (local = fallback
  d'indisponibilité), et GraphHopper offline passe en chantier V1.1.
- entre les deux, OU asymétrie nette par segment → **hybride figé par type de segment**
  (ex. local intra-Paris, attente-Google-300ms-max sur corridors), paramétré, re-testé 2 sem.
- Dans tous les cas : rapport automatique en fin de test → item docket avec la recommandation
  chiffrée ; la bascule d'architecture est une décision utilisateur.

---

## 7. EVENTS (table canonique post-E3, politique E2) — à ajouter au doc 77

| type | émis par | payload minimal |
|---|---|---|
| vtc.assistant.activated / .deactivated / .mode_changed | app | {mode} |
| vtc.offer.logged | sync | {offer_id, verdict, margin, abstained_reason?} |
| vtc.offer.exploration_recorded | nocturne | {offer_id, direction} |
| vtc.model.trained / .deployed / .rejected_by_backtest | §4.4 | {model_kind, version, metrics_ref} |
| vtc.ghost.report_ready | §6 | {period, metrics_ref, recommendation} |
| vtc.surge.capture_requested / .processed | §3.9/§4.6 | {kind, cause_ref?, cells} |
| vtc.reposition.served / .outcome_measured | §3.10/§4.5 | {log_id, followed} |
| vtc.drift.flagged | §4.8 | {metric, value, band, docket_item_id} |
| vtc.template.fix_required | §4.7 | {platform, version, fields} |

correlation_id = session VTC ou dossier d'entraînement ; causation_id = déclencheur direct ;
profondeur = parent + 1. Payloads = références, jamais d'images ni d'adresses clients.

---

## 8. SEEDS & PARAMÈTRES V1 (défauts à valider, versionnés)

h3_res=8 ; pool_window_s=2.5 ; indifference_band=0.10 ; threshold_quantile=0.50 ;
threshold_window_days=28 ; train_window_days=120 ; backtest_days=14 ; exploration_weight=3.0 ;
baggage_buffer_min=30 ; capture_speed_max_kmh=5 ; surge_heartbeat_min=60 ;
endgame_window_min=90 ; ghost_daily_cap=400 ; ocr_audit_pct=20 ; cache TTLs
{traffic:10 min, transports:10, airports:120, thresholds:24 h, zones:30 min, static:8 j} ;
budgets de latence par étage {trigger:250, capture:200, ocr:300, features:50, travel:50,
score:10, render:50} ms — somme cible ≤ 900 ms p95 ; template registry : vide + 1 template
par plateforme construit sur les captures fournies à l'audit (§0.4).

---

## 9. TESTS REQUIS (verrous)

1. **Budget de latence** : harnais sur fixtures (sonnerie simulée + capture fixture) — chaque
   étage sous son budget, total p95 ≤ 900 ms sur 100 runs, sur l'appareil cible.
2. **Micro on-device only** : preuve par revue + test que le tampon audio n'est jamais écrit
   ni transmis (spy filesystem/réseau) ; service actif uniquement si assistant+session.
3. **OCR/templates** : ≥ 98 % champs requis corrects sur 50 fixtures/plateforme ; champ requis
   manquant après double capture → abstention loggée ; template versionné, changement d'UI
   simulé → fix_required émis par la contre-lecture.
4. **Zéro réseau chemin critique** : spy réseau pendant sonnerie→halo = aucun appel ; caches
   stale critique → abstention ; stale secondaire → feature neutralisée.
5. **Estimateur** : pas de double comptage (créneau de pointe : multiplicateur live neutre si
   vitesse courante = attendue du créneau) ; fallback OSM marqué.
6. **Scoreur** : formule cycle complet ; verdict = code ; cas serré coloré (pas d'abstention
   de confort) ; hot-swap modèle jamais pendant un scoring ; version loggée.
7. **Halo** : upgrade-only (fantôme tardif ne rétrograde jamais) ; shadow = pipeline complet,
   halo blanc, logs complets.
8. **Log intégral** : une ligne par sonnerie détectée, y compris abstentions et refus ;
   idempotence de sync (rejeu de batch sans doublon) ; exploration correctement posée dans
   les deux sens.
9. **Entraînement** : verrou de backtest bloque un candidat inférieur (fixture) ; poids
   exploration appliqués ; seuils par sceau avec repli d'effectif.
10. **Fantôme** : horodatages, would_have_arrived correct vs pool_window ; recyclage en
    multiplicateurs ; plafond quotidien + échantillonnage prioritaire près du seuil.
11. **Surge** : cellules vides écrites en intensité 0 ; sollicitations inertes > 5 km/h ;
    calibration couleur→valeur sur cas joint.
12. **Repositionnement** : score net (zone chaude lointaine perd contre tiède proche sur
    fixture) ; pondération fin de session ; fallback hors-ligne marqué ; outcome mesuré à
    +1 h ; followed correct.
13. **E2** : chaîne session → offres → entraînement → déploiement avec
    correlation/causation/profondeur.

---

## 10. ORDRE D'EXÉCUTION ONE-PASS

0. Audit §0 (les deux repos) + VTC_MAPPING.md + captures d'exemple obtenues. STOP si
   l'historique de courses est introuvable.
1. **Tower d'abord** : migrations §5, builders de caches, matrice de base depuis l'historique,
   seuils par période, contrat d'interface §2.3 (schémas JSON + endpoints de sync).
2. Tower : datasets, entraînement nocturne + verrou + export ONNX, modèle de zones, fantôme.
3. **App** : services (audio, capture, overlay), OCR + templates depuis les fixtures,
   assembleur, estimateur, scoreur ONNX, halo, log Room, sync.
4. App : flux surge, bouton « Où je vais », test notification (passif).
5. Tower : contre-lecture P40, prédicteur surge, dérive → docket, rapport fantôme.
6. Tests §9 des deux côtés, harnais de latence sur l'appareil réel.
7. **Rollout gravé** : mode shadow ≥ 2 semaines (halo blanc, tout logge, test fantôme §6
   court en parallèle) → rapport → décision utilisateur → advisory.
8. Docs : nouveau doc numéroté, patch doc 77, VTC_MAPPING final, CI APK verte.

## 11. HORS PÉRIMÈTRE EXPLICITE

- Toute forme d'auto-acceptation ou d'action sur l'app VTC — JAMAIS, pas même en option.
- GraphHopper offline embarqué (V1.1 conditionnée au verdict du test fantôme §6).
- Seuil dynamique piloté par le surge de la zone courante (V2, §4.6).
- LLM où que ce soit dans ce système.
- iOS ; multi-tablettes ; autres régions que l'Île-de-France (matrice et sources IdF).
- Le choix contractuel Google vs TomTom (paramètre provider, les deux implémentés côté
  fantôme, décision coût/quota à l'usage).
- Modification du pipeline OCR P40 existant au-delà de son rôle de contre-lecture.
