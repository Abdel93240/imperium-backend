# SPEC — MINI-PASSE VAULT DÉTERMINISTE V1

> **Livrable d'implémentation one-pass.** Prompt pour Claude Code (Fable 5), exécuté APRÈS le
> socle Toolbox (il consomme runner, parameters, signal_definitions, notifications, events).
> Périmètre : le socle financier déterministe qui manque à tout le monde — moteur de pression
> 0-100 (doc 11), dépenses à venir, profit hebdomadaire. **Zéro IA, zéro GPU, 100 % code +
> SQL.** Consommateurs en attente : rollups W1 (spec WR §4), plan 4 semaines (doc 52 §8.2
> CATEGORY 2), sadaqa The Path (doc 41 §9.2/§16.2), dashboard Vault (doc 42 §14).

---

## 0. MODE D'EMPLOI

**Étape 0** : lire doc 11 (canonique pression — la formule complète y vit), doc 42 (avec le
patch 0-100 appliqué au socle), doc 41 §9/§16, GAP_vault, `78_TOOLBOX_CATALOG.md` (lecture
obligatoire désormais gravée pour toute passe). Vérifier : socle mergé (tables partagées
présentes), ledger canonique `imperium_vault_transactions` avec guards append-only (0033) et
wallet (0037), lecteurs legacy déjà migrés (socle §9). Produire `VAULT_MAPPING.md`.

**Contraintes** : celles du socle. Décisions gravées à encoder sans les rouvrir :
**Q4** échelle 0-100 ; **Q7** la pression n'entre PAS dans la sélection quotidienne Daily
(elle vit en amont, dans le plan) ; **Q9** le profit hebdo naît ici ; **Q10** PAS de docket
Vault propre — les anomalies financières iront au docket WR (par W4, passe WR), Vault
affichera une vue filtrée ; **Q11** la pression est publiée comme SIGNAL dans la table
partagée `signal_definitions`.

**Definition of Done** : migrations + seeds + tests §7 verts + drop de la table orpheline
`vault_transactions` (AD-3 du digest : modèle supprimé au commit 5380399 mais table jamais
droppée — dump pg_dump préalable archivé, puis migration de suppression + retrait de la
route legacy `/api/vault`) + les trois jobs runner
enregistrés (désactivés par défaut) + événements émis avec enveloppe E2 + patch doc 41 §16.2
(pointeur vers la table réelle) + VAULT_MAPPING.md.

---

## 1. SCHÉMA

```sql
CREATE TABLE upcoming_expenses (              -- F2-15 ; source de vérité UTILISATEUR
  id uuid PRIMARY KEY,
  label_fr text NOT NULL,
  amount numeric NOT NULL CHECK (amount > 0),
  due_date date NOT NULL,
  recurrence text,                            -- null|monthly|quarterly|yearly (règle simple V1)
  category text NOT NULL,                     -- aligné sur les catégories du ledger
  wallet text,                                -- aligné migration 0037
  mandatory bool NOT NULL DEFAULT true,       -- doc 11 : incompressible vs ajustable
  active bool NOT NULL DEFAULT true,
  created_at timestamptz, updated_at timestamptz
);

CREATE TABLE weekly_finance_summaries (       -- F2-16 ; la table que doc 42 §16 croyait exister
  week_start date PRIMARY KEY,
  business_revenue numeric NOT NULL,
  business_expenses numeric NOT NULL,
  weekly_business_profit numeric NOT NULL,    -- LE champ que la sadaqa Path lit (doc 41 §16.2)
  personal_expenses numeric NOT NULL,
  computed_at timestamptz NOT NULL,
  detail jsonb NOT NULL                       -- décomposition par catégorie/wallet (auditable)
);

CREATE TABLE pressure_snapshots (             -- historique du score (jamais d'UPDATE)
  id uuid PRIMARY KEY,
  computed_at timestamptz NOT NULL,
  score int NOT NULL CHECK (score BETWEEN 0 AND 100),
  label text NOT NULL,                        -- les 5 labels du doc 11
  factors jsonb NOT NULL,                     -- contributions par facteur (le « Voir pourquoi »)
  daily_targets jsonb NOT NULL,               -- {minimum, comfortable, optimal} €/jour
  inputs_snapshot jsonb NOT NULL              -- entrées figées (reproductibilité)
);
```

## 2. MOTEUR DE PRESSION (module `app/services/vault/pressure.py`)

Implémentation **verbatim de la formule doc 11** (canonique — si un détail du doc est
ambigu, STOP et question, ne pas interpréter) : horizon de dépenses à venir (mandatory
d'abord), solde/coussin par wallet depuis le ledger, revenus attendus, → score 0-100, label
(5 niveaux doc 11), facteurs explicables (chaque terme de la formule avec sa contribution),
objectifs journaliers min/comfortable/optimal. Fonctions : `compute_pressure() ->
PressureResult` + `explain()` (le breakdown, même philosophie que explain_score doc 52).
Publication : chaque calcul écrit `pressure_snapshots` + upsert `signal_values` sur le signal
`vault.pressure` (Q11) dont les bandes sont les 5 labels (seed §5) + event
`finance.pressure.updated` (E2 : causation = la transaction ou l'échéance déclencheuse).

## 3. PROFIT HEBDOMADAIRE

Job `vault.weekly_profit` (runner, cron lundi 00:30 — reprend doc 42 §11 sans n8n) :
agrège le ledger canonique de la semaine close (business vs personnel par catégories/wallets,
mapping en paramètres `vault.category_map`), écrit `weekly_finance_summaries`, émet
`finance.weekly_summary.created`. La sadaqa Path (passe Path) lira `weekly_business_profit`
ici — patch doc 41 §16.2 : « from common memory » → « from weekly_finance_summaries ».
Backfill : à l'activation, calcul rétroactif sur tout l'historique du ledger (idempotent).

## 4. JOBS & DÉCLENCHEURS

`vault.weekly_profit` (cron lundi 00:30) ; `vault.pressure_refresh` (cron quotidien 06:00 +
event_subscription sur `finance.transaction.*` et échéance upcoming_expenses J-7/J-1) ;
`vault.expenses_horizon` (quotidien : échéances proches → notification `normal` à J-7,
`red` si solde wallet < échéance à J-1 — seuils en paramètres).

## 5. SEEDS & PARAMÈTRES

`vault.pressure_thresholds` (bornes des 5 labels, valeurs doc 11) ; `vault.category_map`
(business/personnel — défauts depuis les catégories existantes du ledger, À VALIDER) ;
`vault.horizon_days=45` (doc 11, vérifier) ; signal `vault.pressure` dans
`signal_definitions` (domain=vault, is_medical=false, bandes = labels, baseline_method=none) ;
les 3 job_definitions (enabled=false).

## 6. API (`/api/vault/`)

`GET pressure` (score + label + daily_targets) ; `GET pressure/explain` (facteurs) ;
`GET pressure/history` ; CRUD `upcoming-expenses` (raison non requise — c'est de la donnée
utilisateur, pas une proposition) ; `GET weekly-summaries?from=`.

## 7. TESTS (verrous)

1. Formule dorée : fixtures reproduisant les exemples chiffrés du doc 11 → score/label/targets
   exacts ; si le doc n'a pas d'exemples chiffrés, en construire 5 et les faire VALIDER par
   l'utilisateur avant merge (ils deviennent la référence).
2. Monotonies : dépense mandatory ajoutée → score ne baisse jamais ; revenu encaissé → score
   ne monte jamais (sanity de signe sur chaque facteur).
3. Profit hebdo : fixtures ledger → agrégats exacts, semaines vides = 0 propres, backfill
   idempotent (rejouer = même résultat, pas de doublons).
4. Récurrence upcoming_expenses : génération de la prochaine échéance correcte (monthly/
   quarterly/yearly), pas de duplication.
5. Événements : enveloppe E2 remplie (causation = déclencheur réel) ; notifications J-7/J-1
   avec dedup du socle ; signal `vault.pressure` mis à jour à chaque calcul.
6. Append-only : UPDATE sur pressure_snapshots rejeté ; ledger guards (0033) intacts.
7. Q7 négatif : grep — aucun import de pressure dans les modules Daily (la frontière tient).

## 8. HORS PÉRIMÈTRE

OCR des reçus (doc 42 §6.3, passe ultérieure avec toolbox.ocr) ; catégorisation LLM (42 §7) ;
prévisions/forecasts ; fuel smart tracking (D-07, V2) ; la CONSOMMATION de la pression par le
plan (doc 52 §8.2 — passe WR/plan) et par les rollups W1 (passe WR) ; toute UI Vault.
