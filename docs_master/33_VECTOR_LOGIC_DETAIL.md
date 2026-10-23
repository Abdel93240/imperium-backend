# 33 - Vector Logic Detail

Vector is the VTC profitability intelligence layer.

It is intentionally narrow: it optimizes the user's VTC work, not the user's global life.

## 1. Core Objective

Vector exists to answer one operational question:

```text
What VTC action is most profitable and least wasteful now?
```

That can mean:

- accept or reject a ride recommendation;
- reposition to a zone;
- avoid a dead-return trap;
- wait or move;
- use an event signal;
- exploit a rail disruption;
- avoid road closures;
- protect scheduled ride value.

## 2. Explicit Boundary

Vector does not use the following as decision inputs in V1:

- fatigue;
- sleep quality;
- mood;
- stress;
- family pressure;
- financial pressure;
- global daily objective;
- workout plan;
- worship plan;
- medical data.

Imperium can use those signals globally. Pulse can use health signals. Vault can use finance signals. Vector remains VTC profitability only.

> CODÉ (2026-10-22, migration 20261022_0137, kit Vector final) : pause et reprise d'une session —
> `POST /api/imperium/vector/sessions/{id}/pause` et `/resume` (rejouer sans effet), statut `paused`, `paused_at`,
> `paused_seconds` ; une seule session ouverte (en cours ou en pause) ; arrêter pendant une pause clôt la pause ;
> offres refusées pendant la pause (résultats et recettes acceptés). KPI : `active_minutes` (écoulé moins les
> pauses), `rides_done` (offres acceptées AVEC résultat réel : accepté ≠ réalisé), `rides_refused` ; le CA reste celui
> des résultats écrits au Vault, jamais le nombre de lignes financières.

## 3. VTC Inputs

Vector can use:

- current VTC zone;
- time and day;
- ride price;
- pickup ETA;
- pickup distance;
- estimated trip duration;
- destination zone;
- route and traffic risk;
- road closures;
- rail disruptions;
- event signals;
- airport demand windows;
- scheduled rides;
- fuel/autonomy only when it affects VTC execution;
- historical session outcomes;
- user feedback on recommendation quality;
- **weather** — source: **Open-Meteo** (free, no key, Météo-France AROME model, city-level via coordinates, ~15-min granularity), complemented by **Météo-France department weather alerts** for extreme events. Weather is a **demand signal** (rain/snow → higher demand, higher prices);
- **surge / majoration** — current and recent surge multiplier as a demand & profitability signal. Detailed mechanism (manual capture, OCR, correlation, derived features) lives in **doc 57 §16-17**; doc 33 only references it.

## 4. Ride Offer Score

A ride offer should be scored with VTC economics:

```text
profitability_score = hourly_rate_estimate
                    - dead_return_penalty
                    - pickup_waste_penalty
                    - traffic_risk_penalty
                    + strategic_zone_bonus
                    + event_or_airport_bonus
```

The result is advisory only.

### 4.1 No deceptive averaging when context is incomplete

If the value of a ride depends on a Type 2 variable and that variable is missing,
Vector must not collapse the situation into a generic average. It must abstain.

Examples of Type 2 variables in practice:

- event exit / no event exit;
- airport window / no airport window;
- rail disruption present / absent;
- scheduled ride present / absent.

If the feature is missing, the model must return:

```text
Haute incertitude, à toi de juger.
```

That is better than a biased hourly-rate average.

The ride-offer evaluation (accept-a-ride feature) is **binary**. There are only two real actions when working: take it or don't.

```text
CatBoost ride verdict → 2 outcomes only:
  PROFITABLE     → GREEN halo + "take it" sound
  NOT PROFITABLE → RED halo  + "leave it" sound
(WHITE halo + sound = assistant active / online — not a ride verdict)
```

- Weather and surge feed the score (as inputs, see §3).
- Output is a **signal only**: halo + sound. **No natural-language explanation in real time.** Goal: speed and efficiency while driving, zero friction, zero text.
- The score still includes the existing economics (hourly_rate_estimate, dead_return_penalty, pickup_waste_penalty, traffic_risk_penalty, strategic_zone_bonus, event_or_airport_bonus) — but its **user-facing output** is the binary halo/sound, not a label list.

> CODÉ (2026-10-22/23, lot V2-A, migration 20261022_0138, appli 0.27.0-ocr) — assistant de prise de course. Lecture
> par **capture d'écran + OCR embarqué** sur la tablette (F10 §5-quater, doc 78 F3-05) ; l'accessibilité Android
> n'est jamais utilisée (une première version 0.26.0 qui la lisait a été retirée). L'unique interrupteur de « Ma
> session » demande la capture à chaque lancement (jamais un accord perpétuel) ; service au premier plan avec
> notification « Arrêter ». Lecture **seulement quand l'appli Bolt est affichée** (statistiques d'utilisation
> d'Android, autorisation « accès à l'utilisation » donnée une fois ; appli affichée relue toutes les 200 ms) :
> première image lue aussitôt à l'arrivée de Bolt au premier plan, puis la dernière image toutes les 700 ms tant qu'il
> y reste ; les autres applis ne sont jamais lues (appli 0.28.0-ocr-bolt, décision utilisateur 2026-10-23 ; ce n'est
> pas la capture continue « en arrière-plan » que VECTOR-006 interdit). Image réduite, lue en mémoire, jamais écrite
> ni envoyée ; image entièrement noire = appli qui interdit la capture, dit dans le journal, jamais un
> avis. Reconnaissance d'une offre : prix net (lignes de péage écartées, doc 37 §4), couples durée/distance approche
> puis course, deux codes postaux, programmée, espèces, majoration ; sans prix ni couple, pas d'offre ; un seul code
> postal n'est attribué à aucun côté. Seuls ces champs et la commune partent au serveur (`POST
> …/sessions/{id}/offers`, `source: assistant`) ; le texte lu reste sur la tablette (journal de lecture en mémoire,
> Réglages › Assistant). Statistiques d'usage de la bibliothèque OCR vers son éditeur retirées de l'APK. Halo en
> superposition, sans toucher : vert / rouge selon le signal des règles (doc 57 §3.1), blanc = présence, blanc marqué
> « ? » = aucun avis, gris = pas de session active ou serveur injoignable (jamais favorable). Sons : aigu favorable,
> grave double défavorable, bip à l'activation, aucun son sans avis. La décision (acceptée, refusée, manquée) se
> confirme d'un appui sur le tableau de bord (donnée de comportement). Pas encore : modèle CatBoost (phase règles
> seules), détection automatique de la décision, flux externes, réglage sur les écrans réels de Bolt (le journal sert
> à cela).

> CODÉ (2026-10-23, appli 0.34.0-courses) — lecture calée sur 13 captures Bolt réelles. Offre : puces Priorité,
> gamme (« Bolt »), Carte / Espèces / Client Business, « +x € inclus » (majoration incluse ; avec Priorité, c'est la
> priorité qui la crée), prix « (net, TTC) », couples « 5 min • 1.7 km », adresses (commune et
> quartier, plus l'adresse complète depuis 2026-10-23 : décision utilisateur, la position GPS la donnait déjà), boutons Refuser / Accepter ou Répondre (même sens ; sans eux, pas d'offre). Le serveur déduit
> le code postal et la position de la commune ou du quartier (liste officielle des communes d'Île-de-France, 80
> quartiers de Paris, aéroports ; `services/vector/geo.py`) : arrivée sans code postal résolue, météo de la case
> d'arrivée, distance au centre de Paris. Chronométrage sans saisie : étape d'approche (« En route vers l'adresse de
> prise en charge », « Arrivé ») = acceptation (au plus 5 min après l'offre), « Attente » / « Commencer la course » =
> arrivée, « Finir la course » = départ, « Confirmer le prix » / « Noter le passager » = fin, avec le montant final
> et les espèces ; « Commande annulée » = note sur la décision. À la fin, le résultat part seul : gain (écran de fin,
> sinon puce de course, sinon offre), approche, attente, course à la minute, étapes datées, positions de prise en
> charge et de dépose, paiement ; revenu au Vault (portefeuille cash ou bolt). Les étapes sont vues quand Bolt est à
> l'écran : la bulle Bolt de Waze est désactivée par l'utilisateur (les appuis se font dans Bolt). Le temps de
> retour après dépose reste à 0 (à calculer plus tard depuis l'offre suivante). Courses programmées : dossier V2.

Note: this is the accept-a-ride feature ONLY. **Zone recommendation (§5) is a separate, already-documented feature and is unchanged** — it keeps its short textual reason (the driver is not mid-ride when repositioning, so a brief reason is useful there).

## 5. Zone Recommendation

Vector may recommend:

- stay here;
- move to a named zone;
- return toward Paris;
- move near a station;
- move near an event exit;
- avoid a zone;
- wait for scheduled ride.

Each recommendation must include a short reason.

Example:

```json
{
  "recommendation": "move_to_zone",
  "zone": "Bercy",
  "reason": "Event ending soon, high pickup density expected, low dead-return risk.",
  "confidence": 0.74
}
```

> CODÉ (2026-10-18, migration 0070, sans IA) : `POST /api/imperium/vector/recommendations`
> `{current_zone?}`, `GET …/recommendations/latest`, `GET …/{id}`, `POST …/{id}/feedback`.
> Base : revenus saisis en session avec leur zone (`rides_revenue_entries`), 90 jours, même
> créneau (heure ± 1, semaine ou week-end, Paris), transactions annulées au Vault exclues ;
> une zone n'est comparée qu'avec 5 courses sur 2 sessions au moins. Décision : aucune zone
> comparable → `abstain` (« Haute incertitude, à toi de juger. », §4.1) ; meilleure zone =
> zone actuelle ou gain < 15 % → `stay_here` ; sinon `move_to_zone`. Confiance plafonnée à
> 0,6 ; la raison dit que événements, trains, aéroports et trafic ne sont pas lus
> (`missing_context`). Pas de taux horaire (temps par zone non mesuré). Retour : utile ou
> non, action (accepted|refused|missed|ignored), un seul par recommandation.

## 6. The local model Role in Vector

The split is strict:

- **Ride classification/scoring = CatBoost only** (the ML metric model). The local model does NOT classify rides and does NOT verbalize the verdict in real time.
- Natural-language commentary about rides exists **only after the fact**, in the **Vector report inside the Weekly Review** (built on recorded history), never during live work.
- The local model keeps its non-scoring micro-roles where they make sense off the critical driving path — but not ride scoring and not live ride explanations.

The local model can be called often because Vector needs frequent micro-decisions.

The local model tasks (off the critical driving path):

- classify user feedback;
- summarize why a zone is attractive;
- compare two zones;
- triage ride screenshots after OCR;
- detect bad or incomplete data;
- decide whether escalation is needed.

The local model should not invent data. If a required VTC input is missing, it must ask for clarification or return low confidence.

## 7. Escalation

Escalate to a stronger model only when:

- context is long;
- the decision has high operational impact;
- multiple feeds conflict;
- The local model's confidence is low;
- the user explicitly asks for deeper strategy.

Routine VTC micro-decisions should stay local and cheap.

## 8. Learning Loop

- **CatBoost learns on the OBJECTIVE hourly revenue** = ride earning ÷ **total mobilized time** (approach + wait + ride + estimated return), computed **to the minute** (not in ¼h/½h blocks, which distort short VTC rides).
- **CatBoost does NOT learn on accepted/refused outcome.** A refusal is polluted by fatigue, end-of-day, mood — learning on it would corrupt the profitability model.
- **Refusals ARE recorded** — they are valuable BEHAVIORAL data for the brain (not for CatBoost training). Example: in the Weekly Review the brain can flag "Vector judged these rides profitable, yet you refused many — why?", and cross it with other signals (missed missions, etc.) as a **mental-load / burnout indicator**.
- **WR refinement loop (supervised):** the binary verdict is intentionally imprecise at cold start; the user does not blindly follow it. The Weekly Review analyzes the **gap between CatBoost verdicts and the user's actual decisions** and produces refinement data CatBoost can use to sharpen its business logic. So: CatBoost learns directly on hourly revenue, AND the brain (via WR) prepares supervised corrections from the verdict-vs-decision gap. Raw refusals are never learned directly.

> CODÉ (2026-10-18) : `rides_offers` garde la décision (acceptée, refusée, manquée) comme donnée
> de comportement et le résultat réel des courses acceptées (gain ÷ temps mobilisé à la minute)
> comme cible ; les refus ne servent jamais de cible (doc 57 §6).

## 9. Compliance

Vector never auto-clicks Bolt.

Vector never automates ride acceptance.

Vector only advises. The user decides.

## 10. Future Vector Reports

A future weekly Vector report may summarize:

- best zones;
- worst zones;
- dead-return losses;
- airport timing accuracy;
- event signal accuracy;
- recommendation win/loss rate;
- average hourly rate.

It must not summarize fatigue, personal pressure, health, worship, or global life objectives.
