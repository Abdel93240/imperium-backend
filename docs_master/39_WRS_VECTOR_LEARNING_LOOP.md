# 39 — WR → Vector Learning Loop

This document defines how an approved Weekly Review can improve Vector without mixing Vector with global life planning.

Vector only receives VTC profitability lessons.

## 1. Principle

WR may contain many domains: health, family, money, discipline, work, projects.

Vector must only extract VTC-operational lessons.

Allowed Vector lessons:

- zone performance;
- ride profitability mistakes;
- dead-return patterns;
- airport timing;
- event timing;
- station disruption value;
- traffic/closure impact;
- scheduled ride strategy;
- user feedback about wrong VTC recommendations.

Forbidden Vector lessons:

- fatigue management;
- mood management;
- worship planning;
- workout planning;
- global daily objective pressure;
- family pressure;
- medical context.

Imperium may use those signals elsewhere. Vector does not.

## 2. Flow

1. User approves final WR.
2. Backend stores canonical WR.
3. Backend creates an AI task for module-specific extraction if needed.
4. The local model classifies whether WR contains Vector-relevant VTC lessons.
5. If yes, n8n orchestrates the extraction.
6. The result returns to backend through an authenticated callback.
7. Backend stores approved Vector learning candidates.

No direct DB write by n8n.

## 3. Extraction Output

```json
{
  "module": "vector",
  "source": "weekly_review",
  "week_start": "2026-04-27",
  "lessons": [
    {
      "type": "zone_performance",
      "signal": "Bercy worked well after event exits",
      "confidence": 0.78,
      "evidence": "User reported two good rides after event end."
    },
    {
      "type": "dead_return",
      "signal": "Late ride toward distant suburb caused long empty return",
      "confidence": 0.71,
      "evidence": "WR mentions low net hourly rate after return."
    }
  ],
  "ignored_domains": ["health", "family", "pulse"]
}
```

## 4. Storage Rule

Vector learning candidates should be stored separately from canonical WR.

They are not automatically promoted into hard rules.

A future learning process may promote them after repeated evidence.

## 5. Safety

Vector learning must never create automation that clicks or accepts rides.

Vector learning only changes advice, scoring, and explanations.
