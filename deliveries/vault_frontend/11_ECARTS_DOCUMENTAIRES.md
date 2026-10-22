# Écarts à ne pas reproduire

Constat du checkout lu le 22/10/2026 ; les sources historiques sont conservées comme références et ne remplacent pas les routes réelles.

| Ancienne indication | Règle de cette livraison |
|---|---|
| POST /api/vault/transactions | Supprimé ; utiliser /api/imperium/vault/transactions |
| GET /api/vault/transactions/recent | Absent ; utiliser liste canonique paginée |
| GET /api/vault/pressure/current | Absent ; GET /api/vault/pressure |
| PATCH transaction | Absent ; POST /transactions/{id}/correct |
| Éditer/supprimer une ligne ledger | Append-only : correct/reverse |
| book choisi et envoyé | Catégorie choisie, livre déduit ; aucun book dans DTO create |
| Catalogue catégories /api/vault/categories | GET /api/imperium/vault/categories |
| Catégories personnalisées éditables | CRUD non identifié ; ne pas activer un faux renommage |
| wallet/snapshots/latest | GET /api/vault/wallet pour état courant, /snapshots pour historique |
| cash_eur/bank_eur/crypto_eur en écriture wallet | cash_cents/bank_cents/crypto_cents dans contrat actuel |
| Banque doit toujours être positive | Banque négative autorisée dans les limites du schéma |
| Wallet total = liquidité de survie | Crypto incluse dans visibilité wallet, exclue de pression |
| Titre/status/reminder_days_before d'échéance | label_fr, amount, due_date, active, paid_at ; rappels non éditables ici |
| Toutes mutations dédupliquées | Certaines routes sans Idempotency-Key ; reprise prudente documentée |
| Tous POST succès = action réalisée | Extraction OCR peut retourner status failed ; lire le corps |
| Voir pourquoi = IA | GET pressure/explain déterministe ; advice/detail non présent |
| PATCH settings Vault / réglage sadaqa local | GET settings uniquement ; modifications sadaqa dans Path |
| Deux validations ticket/Pulse | Une validation ; backend écrit dépense + stock sélectionné |
| Échéance handled = dépense payée | Correction pression ≠ mark-paid financier |
| Profit hebdo recalculé par frontend/n8n | Backend runner et weekly_finance_summaries |
| Pression décide directement une mission Daily | Aucun moteur Daily Vault ; contexte amont de planification, règle Q7 |
| Source ancienne 0–10 | Pression 0–100, doc 11 |
| S10 Ultra paysage comme V1 | Décision récente : Tab S8 portrait ; paysage adaptation |
| Snapshot doc 42 marqué futur | Routes et migration 0073 présentes dans le checkout |
| Événements internes = push public déjà disponible | Aucun canal temps réel public présumé |

Des écarts restent ouverts : agrégats pro/perso sur période, filtres exhaustifs, CRUD catégories, voix et conseil. Les boutons non raccordés doivent le dire. Le manifeste contient des empreintes ; si une source change pendant le travail backend concurrent, régénérer le kit et comparer avant intégration. Aucun audit runtime de production n'est revendiqué.
