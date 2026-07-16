# 75 - Mémoire vectorielle unifiée (Imperium) — Référence

> **Statut : document de référence, source de vérité sur la mémoire vectorielle.**
> Issu d'une session de conception complète. Tranche définitivement la question
> « `ai_memories` vs `pgvector_memory` » (doublon relevé par l'audit du 18/06).
> Les patches sur les docs 09, 38, 05, 16, 31, 47 (et autres) DÉCOULENT de ce doc.
> Version amendée du 2026-07-15 (passe 0, Q5 tranchée) : la décroissance par
> exposition non confirmée est NORMATIVE (§0.3/§4 amendés, renvoi spec WR §6.3).
> Cette version amendée datée fait foi.

---

## 0. Décisions verrouillées (résumé exécutif)

1. **Une seule table de mémoire vectorielle**, canonique : **`ai_memories`**.
   `pgvector_memory` (doc 38) est supprimée comme table ; le nom disparaît partout.
2. **On ne vectorise QUE les éléments d'apprentissage** (insight, décision, pattern,
   win, blocker, + futurs — liste OUVERTE, §5bis). Pas les WR complets, pas les
   données structurées, pas la data brute. Le log WR complet reste en texte
   (étage 1), pointé par les éléments d'apprentissage.
3. **Pas de decay temporel.** Le poids-qui-décroît-avec-l'âge de doc 38 est
   SUPPRIMÉ. Un élément d'apprentissage ne vieillit pas avec le TEMPS ; il se
   renforce (confidence) ou se fait corriger (supersession).
4. **`confidence` = solidité par preuve accumulée.** Monte à chaque ré-observation.
   AMENDEMENT (2026-07-15, Q5) : elle ne descend jamais avec le simple passage du
   temps, mais elle PEUT descendre sur **exposition non confirmée** (spec WR §6.3 :
   le prédicat de contexte était rempli, le pattern ne s'est PAS manifesté).
   Une exposition non confirmée est une OBSERVATION négative, pas du temps qui
   passe — le principe « la preuve fait bouger la confiance » est conservé dans
   les deux sens. Le mécanisme (β×confidence, status_multiplier) appartient à la
   spec WR §6.3 ; ce doc grave seulement sa légitimité doctrinale.
5. **Deux patterns contradictoires coexistent** ; le plus prouvé domine ;
   l'ancien survit en trace faible, **jamais supprimé** (valeur historique).
6. **`privacy_level` sur CHAQUE ligne, sans exception.** Garde-fou médical/religieux.
7. **La confiance TRIE, n'EXCLUT jamais.** Aucune recherche ne filtre sur la
   confidence par défaut. Seuls la supersession et le privacy gate excluent.
8. **`source_ref` = chemin vers le CONTEXTE** (le WR riche d'origine + ses patterns
   voisins), pas vers un simple fait.

---

## 1. Le modèle à trois étages

```
ÉTAGE 1 — DONNÉES STRUCTURÉES / SOURCES BRUTES  (recherche PRÉCISE, base classique)
   Faits exacts : "14 nov, 40 L d'essence, zone X", transactions, missions,
   ET les WR complets (texte autosuffisant — voir §6).
   Recherche : exacte, au champ. JAMAIS vectorisée.
   Vit dans : tables métier (Vault, Vector…), fichiers sources (doc 70/20).
        ▲
        │ pointé par source_ref (un chemin, jamais une copie)
        │
ÉTAGE 2 — MÉMOIRE VECTORIELLE = ai_memories  (recherche FLOUE, sémantique)
   UNIQUEMENT des PATTERNS (savoir consolidé : "dort mal → rate ses missions").
   Recherche : par ressemblance de sens. C'est le seul étage vectorisé.
   Seul chercheur : l'IA réflexive (le WR, le conseil stratégique).
```

**Pourquoi ce partage.** La recherche vectorielle sert quand on cherche par
*ressemblance* sans pouvoir nommer le critère exact (« cette semaine ressemble-t-elle
à une mauvaise passe ? »). La recherche structurée sert quand on veut un *fait exact*
(« combien de litres le 14 nov ? »). L'utilisateur et l'IA opérationnelle ne font que
du précis (étage 1). Seule l'IA réflexive a besoin du flou (étage 2).

---

## 2. Ce qui est vectorisé / ce qui ne l'est pas

| Élément | Vectorisé ? | Où il vit |
|---|---|---|
| Élément d'apprentissage (insight, décision, pattern, win, blocker, +futurs) | **OUI** | `ai_memories` (étage 2) |
| Log WR complet (entrée + conversation + sortie) | NON | markdown brut (étage 1), pointé |
| Donnée structurée (essence, montants, dates) | NON | tables métier (étage 1) |
| Décision métier (quel châssis, etc.) | NON | dossier projet (étage 1) |

**Règle anti-double-enregistrement.** Le WR produit des éléments d'apprentissage. On
vectorise ces éléments, PAS le log WR. Le log reste en markdown, et chaque élément
porte un `source_ref` vers lui. L'élément est l'index ; le log riche est le contenu
indexé. Aucune information n'existe en double.

---

## 3. La table `ai_memories` (propriété : doc 09)

Le doc 09 est le propriétaire unique de cette table. Le doc 38 NE définit plus de
table — il ne garde que le *pipeline* ([embedding service], recherche, cron). Schéma fusionné
(base = schéma `ai_memories` existant de doc 09, enrichi des champs utiles de l'ex
`pgvector_memory`) :

```sql
CREATE TABLE ai_memories (
  memory_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

  -- Contenu
  content              TEXT NOT NULL,          -- le pattern en langage naturel
  embedding            vector(1024) NOT NULL,  -- dim 1024 (cf. doc 38, Qwen3-Embedding)
  embedding_model      TEXT NOT NULL,          -- traçabilité du modèle d'embedding

  -- Catégorisation (deux axes distincts)
  memory_type          memory_type NOT NULL,   -- domaine (enum canonique doc 09)
  source_app           source_app NOT NULL,    -- app d'origine (provenance)

  -- Chemin vers le contexte (étage 1) — un POINTEUR, pas une copie
  source_table         TEXT NULL,              -- table/source canonique d'origine
  source_id            TEXT NULL,              -- id dans cette source (ex. le WR)

  -- Solidité par la preuve (PAS de decay temporel)
  confidence           NUMERIC NULL,           -- monte à la ré-observation, ne baisse pas seule

  -- Garde-fou confidentialité — NON NÉGOCIABLE, sur chaque ligne
  privacy_level        privacy_level NOT NULL,

  -- Cycle de vie
  is_active            BOOLEAN NOT NULL DEFAULT true,
  supersedes_memory_id UUID NULL REFERENCES ai_memories(memory_id),
  correction_reason    TEXT NULL,
  expires_at           TIMESTAMPTZ NULL,       -- expiration explicite éventuelle (pas un decay)

  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata             JSONB NULL
);
```

**Champs RETIRÉS de l'ex-`pgvector_memory` et pourquoi :**
- `weight` → **supprimé** (decay temporel tué ; un pattern ne vieillit pas).
- `status` (active/expired/superseded) → remplacé par `is_active` + `supersedes_memory_id`
  (modèle de doc 09, plus explicite).
- `element_type` → fusionné dans `memory_type` (un seul axe de domaine).

**Champs CONSERVÉS de l'ex-`pgvector_memory` :**
- `source_ref_type`/`source_ref_id` → deviennent `source_table`/`source_id` (le chemin).

Index recommandés : index de similarité vectorielle (HNSW, cosine) sur `embedding` ;
`(user_id, source_app, memory_type, is_active)` ; `(user_id, privacy_level, is_active)` ;
`(source_table, source_id)`.

---

## 4. Confidence : la preuve, pas le temps

- Un pattern naît avec une confidence initiale (preuve de départ).
- **Chaque ré-observation fait monter la confidence.** Un pattern re-confirmé
  semaine après semaine devient très solide.
- **Un pattern jamais ré-exposé garde sa confidence figée.** Il ne descend PAS
  tout seul avec le temps. (Il ne devient minoritaire que *relativement* à un
  pattern concurrent qui, lui, accumule des preuves — voir §5.)
- **AMENDEMENT (2026-07-15, Q5) — exposition non confirmée.** Quand le contexte
  du pattern se présente (exposition) et que le pattern ne se manifeste PAS,
  cette non-confirmation est une preuve négative : la confidence descend selon
  la spec WR §6.3. Distinct du decay temporel (toujours interdit) : sans
  exposition, rien ne bouge.
- **Il n'existe AUCUN mécanisme de décroissance temporelle (decay).** C'était la
  logique `weight` de l'ex-doc 38 ; elle est supprimée. Elle résolvait
  l'accumulation des WR — problème dissous puisqu'on ne vectorise plus les WR.

---

## 5. Deux patterns qui se contredisent : coexistence, jamais suppression

Exemple canonique (prières) :
- Pattern A « ne fait pas ses prières à l'heure » (confidence initiale).
- L'utilisateur change → Pattern B « fait ses prières à l'heure » apparaît.
- B est ré-observé chaque semaine → confidence(B) monte. A n'est plus observé →
  confidence(A) reste figée, devient **relativement** minuscule face à B.
- À la recherche « assiduité prières », les deux remontent (proches sémantiquement) ;
  l'IA suit le plus prouvé (B) → « l'utilisateur est devenu assidu ».

**A n'est JAMAIS supprimé.** Il survit en trace faible. Valeur historique : il permet
au WR de parler de progression (« il y a 6 mois tu ne priais pas à l'heure, maintenant
si ») et sert de point d'entrée vers le passé (§7).

**Confidence relative ≠ supersession.** Deux mécanismes distincts, deux situations :
- **Confidence relative** (évolution graduelle) : les deux coexistent, le plus prouvé
  domine, l'ancien reste vrai *historiquement*. Cas prières.
- **Supersession** (`supersedes_memory_id`, correction d'erreur) : un pattern en
  remplace explicitement un autre marqué comme FAUX ; l'ancien est exclu des
  recherches. Cas « ce pattern était une erreur, oublie-le ».
On garde LES DEUX (évoluer ≠ se corriger).

---

## 5bis. Vocabulaire & liste ouverte des éléments d'apprentissage

**Précision de vocabulaire (à ne pas confondre) :**
- **« élément d'apprentissage »** = le terme GÉNÉRAL pour tout ce qui est vectorisé
  dans `ai_memories`. C'est le contenant.
- **« pattern »** = UN type d'élément d'apprentissage parmi d'autres (un croisement
  récurrent). Sens étroit. Ne plus utiliser « pattern » pour désigner l'ensemble.

**Ce qui est vectorisé = les éléments d'apprentissage.** Le partage n'est pas
« pattern vs insight » mais « apprentissage vs data brute / document complet » : un
insight, une décision, un win, un blocker sont des apprentissages (vectorisés), au
même titre qu'un pattern. La data brute et les logs WR complets ne le sont pas.

**Liste V1 des types** (reprise des docs existants) : `insight`, `decision`,
`pattern`, `win`, `blocker`.

**Liste DÉCLARÉE OUVERTE.** De nouveaux types pourront être ajoutés sur le terrain
(ex. « déclic », « obstacle externe »…). Le WR peut PROPOSER un nouveau type quand le
réel en révèle le besoin ; **l'utilisateur valide** (jamais le WR seul). Cohérent avec
la liste ouverte des états-signaux (PATCH 08).

**Règle de sûreté (non négociable pour que l'ouverture soit sans risque) :** le type
est une **étiquette purement descriptive**. AUCUNE logique de traitement ne doit
brancher sur une valeur de type précise (pas de « si type == 'pattern' alors… »). Tous
les éléments d'apprentissage sont vectorisés, cherchés et soumis au privacy gate de
façon **identique**, quel que soit leur type. Le type ne sert qu'à **décrire et
filtrer** (« montre-moi les blockers »). Ainsi, ajouter un type ne casse jamais rien.

---

## 6. Le log WR pointé est RICHE (pas une coquille)

Le `source_ref` d'un élément d'apprentissage pointe vers le **log WR complet** qui l'a
généré. Ce log est un **document markdown autosuffisant**, conservé pour toujours
(étage 1), **jamais vectorisé**, contenant les trois moments :

```
LOG WR COMPLET (markdown, étage 1, conservé pour toujours, JAMAIS vectorisé)
  ├─ Audit d'ENTRÉE   : l'ANALYSE de la data de la semaine (à chaud), y compris les
  │                     axes non saillants ("sommeil : stable, RAS" — utile 6 mois après)
  │                     + un POINTEUR vers la période / les tables sources
  ├─ CONVERSATION     : le dialogue user ↔ IA intégral (réponses, corrections)
  └─ Audit de SORTIE  : synthèse finale validée + éléments d'apprentissage
        │
        │ les éléments d'apprentissage (et EUX SEULS) sont aussi…
        ▼
  VECTORISÉS dans ai_memories (étage 2), chacun avec source_ref → ce log
```

**Règle clé — l'ANALYSE, pas la data brute.** Le log contient l'analyse *de* la data,
PAS la data brute recopiée. La data brute vit à UN seul endroit (les tables métier,
étage 1) ; le log la **référence** par un pointeur, ne la **duplique** pas. Raison :
une seule source de vérité par fait — deux copies finissent par diverger (si la donnée
est corrigée en base, une copie dans le log mentirait). Le texte est gratuit, mais la
non-duplication n'est pas une question de coût, c'est une question de vérité unique.

**Pourquoi le log doit être riche (argument décisif).** L'analyse fine doit être faite
UNE fois, quand la data est fraîche et dense (l'IA de l'époque). 6 mois après, la data
brute a pu être agrégée (cascade temporelle) et a perdu en granularité : réanalyser
donnerait un résultat PIRE. On capture la meilleure analyse possible au bon moment, et
on ne la refait jamais. Le log riche est le contenu ; l'élément d'apprentissage
vectorisé est l'index vers lui.

> Conséquence : la STRUCTURE exacte du log WR (sections obligatoires, format des trois
> moments) est traitée dans la doc du WR (32 / 47), PAS ici. Ce doc-ci pose seulement
> l'exigence : « le log WR pointé doit être riche, autosuffisant, et contenir
> entrée + conversation + sortie ».

---

## 7. Deux modes de recherche (la confiance TRIE, n'EXCLUT pas)

```
RECHERCHE A — "qu'est-ce qui est vrai MAINTENANT ?"
  → recherche sémantique, puis on suit la confidence la plus haute
  → ex : "l'utilisateur est-il assidu ?" → pattern fort "prie à l'heure"

RECHERCHE B — "qu'était-il vrai À L'ÉPOQUE, et pourquoi ?"
  → recherche sémantique SANS filtrer sur la confidence (on veut le faible exprès)
  → on suit son source_ref vers le WR riche d'origine
  → on lit les patterns VOISINS de ce WR pour reconstituer le contexte de vie
  → ex : "pourquoi rechute-t-il ?" → vieux pattern faible "ne priait pas" →
    WR d'il y a 6 mois (riche) → "à l'époque : mauvais sommeil + stress financier"
    → hypothèse pour aujourd'hui, SANS réanalyser la data brute
```

**Règle d'or, non négociable :** la recherche NE filtre JAMAIS sur la confiance par
défaut. La confiance est un signal de TRI (ce qui domine), pas un filtre d'EXCLUSION
(elle ne cache rien). Un pattern à confidence 0,02 reste cherchable — c'est un témoin,
pas un déchet. Les seuls filtres d'exclusion légitimes : la **supersession** (pattern
marqué faux) et le **privacy gate** (niveau non autorisé pour le workflow).

---

## 8. Privacy gate (universel)

`privacy_level` est présent et obligatoire sur **chaque** ligne. La recherche ne
retourne que les niveaux autorisés pour le workflow et le réglage utilisateur. Pour le
contenu sensible (médical, financier, religieux), le recours à l'[embedding service] via
un fournisseur cloud externe est interdit sauf autorisation explicite (cf. doc 09 §Privacy Gate). C'était
le trou de l'ex-`pgvector_memory` (pas de `privacy_level`) — définitivement bouché.

---

## 9. Migration & propagation

- **Migration : triviale.** Les tables sont vides en V1 (système pas en prod, carte
  GPU pas arrivée). Aucune donnée à déplacer : on redéfinit `ai_memories`, on supprime
  la définition de `pgvector_memory`.
- **Propagation du nom** `pgvector_memory` → `ai_memories` (ou renvoi) dans tous les
  docs qui le citent : **16** (archi), **31** (contrat de tâches, `INSERT`), **47**
  (pipeline WR, `INSERT INTO`/`search`), et tout renvoi résiduel. À faire par patches
  ciblés, vérifiés un par un (ne rien casser).
- **Doc 38** : retirer la section « The pgvector_memory Table » ; la remplacer par un
  renvoi « table canonique = `ai_memories`, voir doc 09 » ; conserver tout le reste du
  doc 38 (pipeline de l'[embedding service], recherche, cron) en remplaçant les références au nom.
- **Doc 09** : adopter le schéma de §3 ci-dessus (ajout de `source_table`/`source_id`
  comme chemin explicite si absents ; confirmation que `weight` n'existe pas).
- **Doc 05** : ne définit aucune des deux tables aujourd'hui (vérifié). Si une table
  mémoire y est ajoutée plus tard, elle doit refléter `ai_memories` (§3), nom et colonnes.

---

## 10. Ce que ce document NE traite pas (renvois)

- **Le contenu exact de l'audit de sortie du WR** (structure, sections obligatoires) →
  doc WR (32 / 47). Ce doc pose seulement l'exigence « WR riche et autosuffisant » (§6).
- **Le pipeline de l'[embedding service]** (chunking, modèle, quantification Q8/FP16, hardware) →
  doc 38 (qui garde ce rôle).
- **La cascade d'agrégation temporelle des signaux** → doc 09 (PATCH 08 déjà déployé) ;
  distincte de la présente table de patterns.
- **La vitesse de décroissance / calibration** → le decay TEMPOREL reste sans
  objet (aucune demi-vie). La calibration de la décroissance PAR EXPOSITION
  (β, status_multiplier) appartient à la spec WR §6.3 et à ses paramètres.
```
