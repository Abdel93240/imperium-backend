# PATCH_PULSE — Amendements d'étape 0 pour PULSE_INTELLIGENCE_LAYER_SPEC_V1

Source : audit toolbox 2026-07-10 (`gap_analysis_v1/toolbox/`). Ces amendements modifient
UNIQUEMENT l'étape 0 / les choix d'implémentation de la spec ; ils ne changent pas sa logique
métier. La spec elle-même n'est PAS modifiée par cet audit : l'exécuteur applique ce patch
par-dessus au moment de la passe.

## P-0. Lecture obligatoire à l'étape 0
Ajouter à la liste de lectures §0 : `TOOLBOX_CATALOG_DRAFT.md` (ou son successeur canonique) et
`TOOLBOX_FINDINGS.md`. Toute création de table/service passe d'abord par une vérification au
catalogue (anti-doublon), consignée dans PULSE_MAPPING.md.

## P-0bis. Activation R1 (doc 76)
R1 : TOUT seed (signaux, sentinelle, procédures, coups, rouges) naît `active=false` ;
l'activation est un UPDATE journalisé par vague (doc 76).

## P-1. Tables partagées créées PARTAGÉES d'emblée (confirme le pré-inventaire)
- §3.9 : NE PAS créer `pulse_ai_transition` / `pulse_audit_samples`. Créer directement
  `ai_slot_transition` / `ai_audit_samples` (schéma spec WR §3.7, slots namespacés `pulse.*`)
  + la vue dataset (`v_ai_training_pairs` plutôt que `v_pulse_training_pairs`, §13).
  Justification : spec WR §0 prévoyait une migration pulse_→partagé ; on la supprime à la source
  (FINDINGS DBL-3).
- §3.4 `pulse_parameters` : créer la table PARTAGÉE de paramètres versionnés (même pattern
  append-only, codes namespacés `pulse.*`) — les specs Daily (`df.*`), WR (`wr.*`) et Vector y
  écriront (FINDINGS DBL-4). La vue « current » est générique.
- §3.1 signaux : créer `signal_definitions` / `signal_values` / vue board PARTAGÉES (colonne
  `domain`), seedées avec les 32 signaux Pulse. W4 (spec WR) les réutilisera sans fallback
  (FINDINGS DBL-2).

## P-2. Embedding : dimension et service
- §3.4 `pulse_corpus_sheets.embedding` : **vector(1024)**, pas 4096. Canon = doc 75 §3 / doc 38
  §5.1 / migration `20260705_0032` (la spec disait « vérifier ai_memories » : c'est vérifié,
  c'est 1024). FINDINGS DV-2.
- Le serving d'embedding n'existe pas encore (`embeddings_enabled=False`) : si le socle Toolbox
  (T4) n'est pas livré avant la passe, les embeddings corpus restent NULL + backfill job — ne pas
  bloquer la passe, le consigner dans PULSE_MAPPING.md.

## P-3. Runner unique (pas de nouveaux workflows n8n)
§7 / §14 : le choix « workflow n8n ou runner backend » est TRANCHÉ → runner backend
(`toolbox.runner`, décision utilisateur de sortir n8n de prod). Les 10 « workflows » du §14
deviennent des jobs du runner. Si toolbox.runner n'est pas livré avant la passe : crons APScheduler
minimaux dans le backend, JAMAIS de nouveaux workflows n8n.

## P-4. Notifications
§11 (red flags), §8 (fallback_move « avec notification ») : consommer `toolbox.notifications`
(interface `notify(...)`) — service actuellement stub vide (FINDINGS T1). Si T1 n'est pas livré :
écrire dans une table `notifications` en attente de canal, ne pas inventer un canal ad hoc.

## P-5. Table events canonique
§12 : la table cible est **`events`** (dotted, enveloppe complète, depth ajouté par migration
`20260707_0036`) — PAS `imperium_events` (dépréciée, D2/E3). Les types `pulse.*` du §12 devront
suivre la convention doc 77 (domaine générique : `health.*` plutôt que `pulse.*` — à confirmer
avec le doc 77 au moment du patch doc, cf. FINDINGS DV-11 pour le précédent ghusl).

## P-6. Divers
- §3.5 `pulse_medical_documents.file_ref` : utiliser le pointeur abstrait de rétention doc 70
  (NAS-ready) plutôt qu'un chemin local en dur.
- §6 interprète : le wrapper LLM contraint créé ici (GBNF, retry, dry-run, tiers) est
  `toolbox.llm` — le construire dans `services/ai/` (pas `services/pulse/`), car WR §15.3 et
  Daily §8 le réutilisent tel quel.
- Étape 0 : `imperium_pulse_entries` (migration 0028) est la seule table santé existante —
  les tables `meals`/`workouts`/`food_stock_items` annoncées par doc 40 N'EXISTENT PAS
  (FINDINGS DV-3) ; le PULSE_MAPPING.md doit les classer « créer », pas « étendre ».
