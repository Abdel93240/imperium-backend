"""Cas dorés : couvrent chaque tranche de chaque critère (deadline en jours relatifs à aujourd'hui)."""
CASES = []
domains = ["religious", "business", "finance", "health"]
# A — deadline : chaque tranche + absente
for i, d in enumerate([-3, 0, 1, 2, 3, 6, 7, 14, 15, 30, 31, 90, None]):
    CASES.append({"domain": domains[i % 4], "deadline_days": d, "impact": "important", "mission_type": "cat_e",
                  "dependency": "none", "recurrence": "weekly"})
# B — impact : chaque libellé + entier + legacy + absent
for i, v in enumerate(["cosmetic", "quality_of_life", "quality-of-life", "mid", "paperwork", "important", "critical",
                       "vital_short_term", "vital-immediate", 17, 99, "Critical"]):
    CASES.append({"domain": domains[i % 4], "deadline_days": 5, "impact": v, "mission_type": "cat_b"})
CASES.append({"domain": "business", "deadline_days": 5, "impact_points": 22, "mission_type": "cat_b"})
CASES.append({"domain": "business", "deadline_days": 5, "impact_level": 40})
# C — type : chaque catégorie, alias, effort, legacy
for i, v in enumerate(["cat_a", "cat_b", "cat_c", "cat_d", "cat_e", "cat_f", "cat_g", "cat_h", "cat_i",
                       "vital_immediate", "legal_contractual", "medical_planned", "religious_obligatory",
                       "work_income", "learning", "health_routine", "quality_of_life", "optional"]):
    CASES.append({"domain": domains[i % 4], "deadline_days": 10, "impact": "mid", "mission_type": v,
                  "dependency": "multiple", "recurrence": "monthly"})
CASES.append({"domain": "health", "deadline_days": 10, "impact": "mid", "effort": "cat_c"})
CASES.append({"domain": "health", "deadline_days": 10, "impact": "mid", "effort_points": 13})
CASES.append({"domain": "health", "deadline_days": 10, "impact": "mid", "mission_type_points": 25})
# D — dépendance : libellés, booléens, points, compte bloqué
for i, v in enumerate(["none", "no", "false", "one_two", "one-two", "some", "true", "multiple", "many", True, False, 7]):
    CASES.append({"domain": domains[i % 4], "deadline_days": 20, "impact": "critical", "mission_type": "cat_d",
                  "dependency": v, "recurrence": "yearly"})
for i, n in enumerate([0, 1, 2, 3, 9]):
    CASES.append({"domain": domains[i % 4], "deadline_days": 20, "impact": "critical", "mission_type": "cat_d",
                  "blocked_mission_count": n, "recurrence": "daily"})
CASES.append({"domain": "finance", "deadline_days": 20, "dependency_points": 8})
# E — récurrence : libellés, alignment, legacy
for i, v in enumerate(["daily", "quotidien", "weekly", "hebdomadaire", "monthly", "mensuel", "yearly", "annual",
                       "annuel", "exceptional", "unique", 4]):
    CASES.append({"domain": domains[i % 4], "deadline_days": 1, "impact": "vital_immediate", "mission_type": "cat_a",
                  "dependency": "many", "recurrence": v})
CASES.append({"domain": "religious", "deadline_days": 1, "alignment": "monthly"})
CASES.append({"domain": "religious", "deadline_days": 1, "alignment_points": 6})
# Vide, plein, payload douteux, buckets bas
CASES.append({"domain": "finance"})
CASES.append({"domain": "religious", "deadline_days": 0, "impact": "vital_immediate", "mission_type": "cat_a",
              "dependency": "multiple", "recurrence": "exceptional", "payload": {"api_key": "x", "note": "y"}})
CASES.append({"domain": "health", "deadline_days": 90, "impact": "cosmetic", "mission_type": "optional",
              "dependency": "none", "recurrence": "daily"})
