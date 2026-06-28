# GAP Analysis V1 - Vault / Finance

Date: 2026-06-28  
Scope: lecture docs -> gap V1. Aucun code backend audite a nouveau, aucun code modifie.

## Base de comparaison

Source "deja code" imposee par la tache, sans re-audit:

- `imperium_vault_transactions` canonique: montants en cents, reversals, API append-only.
- `vault_transactions` legacy: a debrancher.
- `backend/app/services/vault/`, `backend/app/services/imperium/vault`, routes `/api/vault` et `/api/imperium/vault`.
- Dashboard Vault summary.

Important: le present rapport cherche les capacites V1 reclamees par la doc mais absentes du perimetre ci-dessus. Il ne juge pas la conformite fine du code existant.

Docs lues:

- `docs_master/27_VAULT_TRANSACTIONS_WORKFLOW.md`
- `docs_master/42_VAULT_LOGIC_DETAIL.md`
- `docs_master/11_FINANCIAL_PRESSURE_FORMULA.md`
- contexte deja code: `audit_resync/AUDIT_vault.md`

## Lecture de version

| Feature / capacite Vault | Version cible d'apres doc | Statut code selon base imposee | Passage source |
|---|---:|---|---|
| Capture manuelle de transaction financiere | V1 | Code | doc 27: "Vault V1 supports manual financial transaction capture and a live weekly summary" lignes 5-5 |
| Transaction auth + idempotency | V1 | Code | doc 27: headers `Authorization` / `Idempotency-Key` lignes 61-66, comportement idempotent lignes 87-92 |
| Liste recente des transactions | V1 | Code | doc 27: endpoint recent lignes 120-127 |
| Resume hebdomadaire live | V1 | Code | doc 27: summary live, pas de table materialisee en V1 lignes 129-137 |
| Correction / reversal append-only | V1 | Code | doc 27: correction V1 lignes 168-172; base imposee: reversals canonique deja codes |
| Event `vault.transaction.created` | V1 | Code partiel / dette canonique | doc 27: append event lignes 87-90 et event type lignes 174-180 |
| Deux livres business/personnel | V1 | GAP | doc 42 status "Vault V1 reference" lignes 570-571; architecture deux livres lignes 36-82 |
| Revenus/depenses business + personal separes | V1 | GAP | doc 42: Vault can track income/expenses separated lignes 14-17 |
| Categories par livre + categories custom | V1 | GAP | doc 42: categories par flow lignes 146-149 et 168-179 |
| Wallet total cash + bank + crypto, mise a jour manuelle | V1 | GAP | doc 42: bank V1 manual, crypto V1 manual lignes 86-104; refresh lignes 231-241 |
| Sync bancaire automatique | V2 | Hors V1 | doc 42: bank V2 automatic via banking API lignes 94-98 |
| Sync crypto automatique | V2 | Hors V1 | doc 42: crypto V2 automatic via exchange API lignes 99-102 |
| Predicted wallet apres transactions + alerte ecart > 5% | V1 ? a confirmer | GAP | doc 42: wallet adjustment lignes 244-254; pas de tag V1 local sauf status global V1 |
| Liste de depenses recurrentes user-owned | V1 | GAP | doc 11: document V1 lignes 5-13; recurring expenses source of truth lignes 39-50 |
| Upcoming expenses manuelles + alerts | V1 | GAP | doc 42: upcoming_expenses table lignes 300-319; dashboard alerts lignes 382-388; email parsing reporte V2 ligne 319 |
| Classification required/deferrable pour depenses hors liste | V1 ? a confirmer | GAP | doc 11: scoring lignes 61-76; poids exacts encore TODO ligne 759 |
| Score de pression financiere 0-100 deterministe | V1 | GAP | doc 11: V1 formula lignes 5-13, inputs V1 lignes 78-104, overview lignes 131-145 |
| Labels `safe/stable/attention/pressure/critical` | V1 | GAP | doc 11: output + labels lignes 106-129 et 339-347 |
| Formule required money / realistic capacity + modifiers | V1 | GAP | doc 11: steps lignes 147-337 |
| Objectifs journaliers minimum/comfortable/optimal | V1 | GAP | doc 11: daily objectives lignes 349-409 |
| Explication obligatoire du score | V1 | GAP | doc 11: user trust rule lignes 411-431 |
| Corrections manuelles pressure: postponed/handled/exceptional | V1 | GAP | doc 11: manual correction lignes 433-449 |
| Stockage pressure snapshots / weekly financial snapshot | V1 ? a confirmer | GAP | doc 42: `vault_pressure_snapshots` to add lignes 505-512; doc 11 fields recommended lignes 462-529; table name encore TODO ligne 757 |
| Weekly business profit lundi 00:30 + event sadaqa | V1 ? a confirmer | GAP partiel | doc 42: workflow n8n lignes 323-350; conflit doc 27 qui exclut n8n et materialized summaries de ce workflow lignes 7-15 |
| Base sadaqa = profit reel business | V1 | GAP | doc 42: business profit feeds Path lignes 54-55 et 77-81; doc 11 sadaqa lines 531-560 |
| Path donation -> Vault expense `Sadaqa` | V1 ? a confirmer | GAP | doc 42: backend writes corresponding expense lignes 411-418 |
| Receipt scan / OCR / draft transactions | V1 ? a confirmer | GAP | doc 42: receipt flow lignes 182-199; UI V1 quick action ligne 538 |
| Receipt food items -> Pulse stock | V1 ? a confirmer | GAP | doc 42: Pulse integration lignes 420-428 |
| Categorization suggestion via local model | V1 ? a confirmer | GAP | doc 42: local layer lignes 123-127; initial categorization lignes 203-216 |
| `user_category_memory` + repeated high-confidence suggestion | V1 ? a confirmer | GAP | doc 42: repeated categorization lignes 218-225; table lignes 494-503 |
| Level 2 "Voir pourquoi" advice | V1 ? a confirmer | GAP | doc 42: advice endpoint/task lignes 379-403 |
| Vault AI task types / routing distribution | V1 ? a confirmer | GAP | doc 42: AI task types lignes 355-363; routing distribution lignes 367-375 |
| Vector reads fuel history; VTC session writes confirmed Vault income | V1 ? a confirmer | GAP | doc 42: Vector integration lignes 430-440 |
| Imperium reads pressure, week balance, alerts | V1 | Code partiel / GAP | doc 42: Imperium reads Vault summaries lines 443-456; dashboard summary code, pressure/alerts gap |
| Android Vault UI surface | V1 ? a confirmer pour ce repo backend | Hors backend code | doc 42: UI Surface V1 lignes 525-555; doc 27 exclut UI du workflow lignes 7-15 |
| Email auto-detection of upcoming expenses | V2 | Hors V1 | doc 42: "V2 may auto-detect from email parsing" ligne 319 |
| Negative corrections via `amount_delta` | Futur | Hors V1 | doc 27: "If negative corrections are needed later..." lignes 168-172 |
| Monthly analysis / strategic reporting | V1 ? a confirmer / plutot hors coeur V1 operationnel | Hors V1 immediat | doc 11: monthly view may exist strategic reporting ligne 37; doc 42 monthly cloud task lignes 360 et 373 |

## ✅ Code V1

Ces elements sont reclames en V1 et couverts par le perimetre "deja code" impose:

- Ledger de transactions: creation manuelle de revenus/depenses, montant positif, devise, categorie, notes/date/source.
- API transaction avec auth et idempotency.
- API append-only canonique avec reversals sur `imperium_vault_transactions`.
- Liste/lecture de transactions et services/routes Vault existants.
- Resume financier live et dashboard Vault summary.
- Resume par categorie / lecture de synthese deja presente dans le module Vault Imperium.

Dette a garder visible: doc 27 decrit `vault_transactions`, alors que le canonique actif demande par la tache est `imperium_vault_transactions`. Cette dette documentaire ne doit pas masquer que la capacite ledger de base existe.

## 🔲 GAP V1

### 1. Deux livres business/personnel

Ce qui manque:

- Champ ou modele canonique `book = business | personal` sur les transactions canonique Vault.
- Validation API create/update contract autour du livre.
- Totaux separes business/personnel sur semaine/mois.
- Filtres de lecture par livre.
- Categories par defaut distinctes par livre.

Tables / contrats affectes:

- `imperium_vault_transactions` ou table canonique equivalente.
- Schemas request/response `POST /api/imperium/vault/transactions`.
- Endpoints summary semaine/mois/categories.

IA/GPU:

- Deterministe, codable maintenant.

Pourquoi V1:

- doc 42 declare Vault V1 reference lignes 570-571.
- doc 42 dit que Vault track income/expenses business + personal separated lignes 14-17.
- doc 42 presente la Two-Book Architecture comme concept le plus important lignes 36-82.

### 2. Wallet snapshots cash/bank/crypto manuels

Ce qui manque:

- Table `vault_wallet_snapshots` ou equivalent canonique.
- Endpoint pour enregistrer un snapshot manuel cash/bank/crypto.
- Endpoint de lecture dernier snapshot + total wallet.
- Integration du dernier snapshot dans la pression financiere.

Tables / contrats affectes:

- Nouvelle table `vault_wallet_snapshots`.
- Contrats `/api/imperium/vault/wallet-snapshots` ou endpoint Vault equivalent.
- Dashboard summary Vault.

IA/GPU:

- Deterministe, codable maintenant.

Pourquoi V1:

- doc 42 indique bank V1 manual et crypto V1 manual lignes 94-102.
- doc 42 decrit manual wallet refresh et insert dans `vault_wallet_snapshots` lignes 231-241.

### 3. Upcoming / recurring expenses et alertes

Ce qui manque:

- Table d'obligations recurrentes avec `label`, `recurrence`, `amount`, `category`, `payment_day_of_month`.
- Table ou vue `upcoming_expenses` avec status pending/paid/overdue, due date et reminders.
- CRUD manuel pour ces obligations.
- Calcul des obligations dues dans la fenetre operationnelle.
- Alertes next 7 days / overdue exposees au dashboard et a Imperium.

Tables / contrats affectes:

- Nouvelle table recurring expenses, ou extension de `upcoming_expenses`.
- Nouvelle table `upcoming_expenses` si separee.
- Endpoints CRUD obligations / upcoming expenses.
- Dashboard Vault + Imperium context.

IA/GPU:

- Deterministe pour la liste user-owned et les alertes.
- Classification des depenses hors liste est a confirmer separement.

Pourquoi V1:

- doc 11 est une formule V1 lignes 5-13 et fait de la recurring-expenses list un input source of truth lignes 39-50.
- doc 42 decrit `upcoming_expenses` et precise que l'auto-detection email est V2, donc la saisie manuelle reste V1 lignes 300-319.

### 4. Financial pressure score 0-100

Ce qui manque:

- Service deterministe de calcul `financial_pressure_score`.
- Inputs normalises: current week income, expected income, charges, overdue, wallets cash/bank, fuel, remaining work days, realistic capacity, survival threshold.
- Score final 0-100, label canonique, base ratio, modifiers.
- Explanation structure exposee au dashboard et a Imperium.
- Tests unitaires de formule sur les cas A-D de la doc.

Tables / contrats affectes:

- Service Vault pressure.
- Endpoint lecture pressure actuelle.
- Stockage snapshot a confirmer (`vault_pressure_snapshots` ou weekly snapshot).
- Dashboard Vault et consommation Imperium/Vector.

IA/GPU:

- Deterministe. Pas d'IA pour le score.
- Peut consommer des inputs venant d'autres modules, mais la formule elle-meme est codable maintenant avec inputs explicites.

Pourquoi V1:

- doc 11: "defines the V1 deterministic formula" lignes 5-13.
- doc 11: required V1 inputs lignes 78-104.
- doc 11: no AI weighting in V1 lignes 131-145.
- doc 11: formula et labels lignes 147-347.

### 5. Daily financial targets issus de la pression

Ce qui manque:

- Calcul de `daily_minimum_target`, `daily_comfortable_target`, `daily_optimal_target`.
- Exposition a Imperium pour sizing mission / objectif VTC.
- Warning si minimum > capacite realiste.

Tables / contrats affectes:

- Pressure response model.
- Imperium daily planning context.
- Eventuel weekly financial snapshot.

IA/GPU:

- Deterministe, codable maintenant si `realistic_daily_capacity` et work days sont fournis.
- Source exacte de capacite realiste reste une decision ouverte doc 11.

Pourquoi V1:

- doc 11: daily objectives must come from obligations, workdays, capacity lignes 349-356.
- formules lignes 358-409.

### 6. Manual corrections pour pressure

Ce qui manque:

- Actions utilisateur: mark expense postponed, handled, exceptional week.
- Evenements append-only pour chaque correction.
- Recalcul et snapshot de pression apres correction.
- Explication qui affiche la correction sans effacer l'historique.

Tables / contrats affectes:

- `upcoming_expenses` / recurring obligations.
- Event log.
- Pressure snapshot.
- Endpoints correction.

IA/GPU:

- Deterministe, codable maintenant.

Pourquoi V1:

- doc 11: manual correction requirements lignes 433-449.

### 7. Sadaqa basis depuis profit business reel

Ce qui manque:

- Profit business hebdomadaire fiable, separe du personnel.
- Contrat de lecture pour Path: sadaqa base = real weekly profit.
- Event ou donnees communes permettant a Path/Imperium de lire ce profit.

Tables / contrats affectes:

- Transaction canonique avec `book`.
- Weekly finance summary ou live weekly business profit.
- Integration Path read model.

IA/GPU:

- Deterministe, codable maintenant apres deux-book architecture.

Pourquoi V1:

- doc 42: business profit feeds Path lignes 54-55 et 77-81.
- doc 11: sadaqa base = real weekly profit lignes 531-560.

### 8. Imperium consumption complet: pressure + alerts

Ce qui manque:

- Imperium lit deja un summary Vault, mais les signaux V1 complets manquent: pressure daily et upcoming_expenses_alert.
- Contrat stable pour daily planning: pressure label, reasons, daily targets, alerts.

Tables / contrats affectes:

- Vault pressure endpoint/read model.
- Imperium daily planning context.

IA/GPU:

- Deterministe pour l'exposition des signaux.

Pourquoi V1:

- doc 42: Imperium reads `pressure_score`, `week_balance`, `upcoming_expenses_alert` lignes 443-456.

## V1 ? à confirmer

Ces capacites apparaissent dans une doc Vault V1 ou une formule V1, mais la version exacte est ambigue, contradictoire, ou depend d'un service IA/non-backend. Elles ne doivent pas etre tranchees sans validation utilisateur.

| Item | Pourquoi confirmer | Ce qu'il faudrait si valide V1 | IA/GPU |
|---|---|---|---|
| Predicted wallet + prompt ecart > 5% | Dans doc 42 V1 reference, mais pas de tag V1 local. | Calcul predicted wallet depuis dernier snapshot + transactions; champ dans dashboard; seuil 5%. | Deterministe |
| Stockage pressure snapshots / weekly financial snapshot | doc 42 demande `vault_pressure_snapshots`, doc 11 recommande des champs, mais doc 11 garde le nom exact en TODO. | Table snapshot + endpoint latest/history + retention. | Deterministe |
| Weekly profit computation n8n lundi 00:30 + event | doc 42 le decrit, mais doc 27 exclut n8n/materialized weekly summaries de ce workflow V1. | Trigger backend appele par n8n, calcul business profit, event `vault.weekly_profit.computed`. | Deterministe |
| Classification required/deferrable des depenses hors liste | doc 11 la decrit, mais les poids exacts sont TODO. | Grille de scoring, garde-fous vital/legal, explication uncertainty. | Peut impliquer IA locale pour cas ambigus; pas GPU obligatoire |
| Categorization suggestion + `user_category_memory` | doc 42 decrit local model et table, sans tag V1 local. | Table memory, endpoint suggestion, validation user, auto-suggest apres 3 occurrences. | Local model pour premiere suggestion; application deterministe apres validation |
| Receipt scan OCR + draft transactions | doc 42 l'inclut et UI V1 montre "Scan ticket", mais doc 27 exclut AI/UI de son workflow. | Upload media, ai_task `vault.receipt_extract`, draft transaction, validation endpoint. | OCR service / Gemini probable; pas necessairement GPU local |
| Receipt food items -> Pulse stock | Dependant du receipt scan. | Transaction Vault + ecriture Pulse via backend brain rule. | OCR pour extraction; ecriture deterministe |
| Path donation -> Vault expense `Sadaqa` | Integration de domaine decrite, pas tag version explicite hors status global V1. | Endpoint/event Path confirme donation; backend cree depense Vault. | Deterministe |
| Vector fuel history + session income write | Integration decrite, pas tag version explicite. | Read model fuel expenses; endpoint/event session confirmed -> Vault income. | Deterministe |
| Level 2 "Voir pourquoi" advice | UI V1 le montre, mais c'est on-demand local model. | Endpoint `/api/vault/advice/detail`, ai_task `vault.detailed_advice`. | Local model |
| Vault AI task catalog/routing | Listee dans doc 42, mais certaines taches sont mensuelles/WR. | Declarer contrats ai_task et routage minimal. | Local/cloud selon tache |
| Android Vault UI V1 | doc 42 UI V1, mais ce repo est backend et doc 27 exclut UI du workflow. | Non applicable backend sauf contrats API supports. | N/A |

## ⏳ Hors V1

- Bank sync automatique via banking API: V2 explicite.
- Crypto sync automatique via exchange API: V2 explicite.
- Auto-detection email des upcoming expenses: V2 explicite.
- Negative corrections via migration `amount_delta`: futur explicite.
- Monthly cloud finance analysis: a garder hors coeur V1 operationnel tant que le daily/weekly deterministic core n'est pas complet.
- Weekly review contribution high reasoning: a traiter avec le domaine Weekly Review, pas comme prerequis Vault V1 minimal.
- UI polish/animations: hors priorite backend V1.

## GAP V1 priorise

Ordre conseille pour rester fidele au MVP backend-first:

1. Ajouter la separation business/personnel au ledger canonique.
2. Ajouter wallet snapshots manuels cash/bank/crypto.
3. Ajouter recurring/upcoming expenses manuelles + status overdue/paid/postponed.
4. Implementer la formule pressure 0-100 avec tests doc 11.
5. Exposer daily financial targets + pressure explanation a Imperium.
6. Brancher sadaqa basis sur profit business reel.
7. Seulement apres: categorisation locale, OCR ticket, advice detail.

## Suggestion d'enrichissement `docs_master/_CATALOG.yaml`

Ne pas appliquer automatiquement dans cette campagne; proposition pour sortir les docs de `to_review`.

```yaml
- file: "27_VAULT_TRANSACTIONS_WORKFLOW.md"
  number: 27
  title: "Vault Transactions Workflow"
  family: architecture
  categories: [workflow, app:vault]
  status: needs_alignment
  version: v1
  source_of_truth_for: ["legacy vault transaction workflow", "manual transaction capture v1"]
  notes: "Describes `vault_transactions` and /api/vault legacy path. Needs alignment with canonical `imperium_vault_transactions`, cents, reversals, and /api/imperium/vault."

- file: "42_VAULT_LOGIC_DETAIL.md"
  number: 42
  title: "Vault Logic Detail"
  family: architecture
  categories: [app:vault]
  status: needs_alignment
  version: v1
  source_of_truth_for: ["vault product logic", "vault v1 capability map"]
  depends_on: [11, 27, 41, 43]
  notes: "V1 reference but over-claims implemented schema (`weekly_finance_summaries`) and still names `vault_transactions`; align with canonical ledger and split V1 vs V1? items."

- file: "11_FINANCIAL_PRESSURE_FORMULA.md"
  number: 11
  title: "Financial Pressure Formula"
  family: architecture
  categories: [app:vault, app:imperium]
  status: needs_alignment
  version: v1
  source_of_truth_for: ["financial pressure formula v1", "daily financial targets"]
  notes: "Formula is V1 deterministic and usable, but doc 42 still summarizes pressure as 0-10 while doc 11 defines 0-100; open decisions remain for capacity source, weekly boundary, confidence and table name."
```
