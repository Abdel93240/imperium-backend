# Patch FACT-1 — Corrections factuelles rapides (docs 07, 12, 29, 32)

Quatre corrections factuelles issues de la relecture (passe 1). Chacune indique
le remplacement exact à appliquer en place.

---

## 07-1 — Doc 07 : bouton commencer ET finir le jour

Fichier : `07_ANDROID_APP_RESPONSIBILITIES.md`, dans les responsabilités Imperium.

Remplacer :
```text
- finish day button
```
par :
```text
- start day button
- finish day button
```

Raison : Imperium doit exposer le bouton **commencer le jour** ET **finir le
jour** (pas seulement finir). Cohérent avec doc 12 §"Definition of Operational
Day" qui borne le jour par start→finish.

---

## 12-1 — Doc 12 : une journée opérationnelle peut dépasser 24h

Fichier : `12_DAILY_OBJECTIVE_PERIOD_LOGIC.md`, section `## Definition of
Operational Day`.

Après le bloc :
```text
The operational day starts when user starts the day.
The operational day ends when user presses Finish Day.
```
ajouter :
```text
An operational day can therefore last MORE than 24 hours (it is bounded by
start→finish, never by a midnight reset). This is not a problem: it simply means
following days may be shorter (e.g. a 6-hour day after a long one). The
ecosystem reasons in operational days, not calendar days.
```

Raison : le découpage start→finish autorise déjà des journées >24h, mais ce
n'était pas dit explicitement ni sa conséquence (journées suivantes plus courtes).

---

## 29-1 — Doc 29 : Weekly Report ≠ Weekly Review

Fichier : `29_WEEKLY_REPORT_WORKFLOW.md`, juste après le titre / au début du Scope.

Ajouter un encart en tête de doc :
```text
> ⚠️ NAMING — do not confuse:
> - This doc (29) = **Weekly Report**: a deterministic, read-only report
>   (no AI, no n8n, no writes).
> - Doc 32 = **Weekly Review (WR)**: the interactive AI conversation.
> "Report" and "Review" are two different objects. WR always means Weekly Review.
```

Raison : lever toute confusion entre le Report (29) et la Review (32).

---

## 32-1 — Doc 32 : WR = Weekly Review uniquement

Fichier : `32_WR_INTERACTIVE_WORKFLOW.md`, ligne 3.

Remplacer :
```text
WR means **Weekly Review / Weekly Report**.
```
par :
```text
WR means **Weekly Review** (NOT Weekly Report). The deterministic read-only
"Weekly Report" is a separate object, defined in doc 29. Throughout the
ecosystem, "WR" always means Weekly Review.
```

Raison : le doc se contredisait en disant "Review / Report". On tranche : WR =
Weekly Review, et on renvoie au doc 29 pour le Report.

---

## Notes
- 07-1, 12-1, 32-1 : remplacements à motif unique, sûrs.
- 29-1 : ajout d'un encart en tête (pas de remplacement).
- Ces 4 corrections n'ont aucune dépendance entre elles ; applicables dans
  n'importe quel ordre.
