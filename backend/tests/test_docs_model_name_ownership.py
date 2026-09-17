"""Documentary ownership invariant for concrete AI model names in docs_master.

Rule (doc 30 §0 / §3, F10 header):
- doc 30 §3 is the ONLY owner of the logical ROLE -> concrete model/version mapping;
- F10 owns the physical/technical local deployment only (GPU, GGUF, quant, runtime…);
- every other spec names generic roles (local_executor, first_cloud_tier, …).

Same family of repo invariant as `test_toolbox_roles_dv6.py` (grep-style, hermetic,
pure file reading): historical audits / applied patches / SQL examples may keep the
old names for traceability, everything else must stay role-based.

2026-09-17 mapping update: Sonnet 5 / Opus 5 / Fable 5.1 / GPT-5.6 Sol / GPT-6 Astra,
plus the new role `high_reasoning_safeguard` (§3.8quater) that owns the §5.6
independent re-scoring. The Anthropic-native Fable content safeguard (§3.7) must stay
a distinct mechanism and never be relabelled as that role.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_MASTER = BACKEND_ROOT.parent / "docs_master"

DOC_30 = "30_AI_ROUTING_AND_SCORING_POLICY.md"
DOC_F10 = "F10_TOPOLOGIE_INFRA.md"

# Concrete artefact currently serving `local_executor` (doc 30 §3.3 / F10 §5-ter).
LOCAL_EXECUTOR_MODEL = "Qwen3.6-27B-Q6_K"

# Canonical ROLE -> (concrete model, API identifier or None) — doc 30 §3 (2026-09-17).
CANONICAL_MAPPING: dict[str, tuple[str, str | None]] = {
    "local_executor": (LOCAL_EXECUTOR_MODEL, None),
    "first_cloud_tier": ("Claude Sonnet 5", "claude-sonnet-5"),
    "high_reasoning": ("Claude Opus 5", "claude-opus-5"),
    "sustained_long_context": ("Claude Fable 5.1", "claude-fable-5-1"),
    "health_specialist": ("GPT-5.6 Sol", None),
    "finance_specialist": ("GPT-5.6 Sol", None),
    "web_fresh_data": ("GPT-5.6 Sol", None),
    "high_reasoning_safeguard": ("GPT-6 Astra", "gpt-6-astra"),
}

# Historical corpora that photograph a past state (kept on purpose, annotated as such).
HISTORICAL_DIRS = {"_patches_to_apply"}
HISTORICAL_FILES = {
    "99_AUDIT_COHERENCE_DOCS.md",  # historical audit (header says so)
    "99_REGLES_NOMENCLATURE_DOCS.md",  # historical execution plan quotes the old names
}

# --- Group A: obsolete local runtime / obsolete local model artefacts -----------------
# Must never appear as a normative statement outside doc 30 §3 / F10.
STALE_LOCAL_RUNTIME = re.compile(
    r"Qwen3-32B|qwen3:32b|Qwen ?32B|Q5_K_M|\bOllama\b|\bvLLM\b", re.IGNORECASE
)
STALE_LOCAL_RUNTIME_ALLOWED = HISTORICAL_FILES | {
    "31_AI_TASKS_AND_RESULTS_CONTRACT.md",  # Patch 2E block explicitly marked historical
    "56_AUTONOMOUS_CODING_ORCHESTRATOR.md",  # build orchestrator, not Imperium AI routing
    "78_TOOLBOX_CATALOG.md",  # F2-17: historical seed 0039 id `qwen3-32b`, annotated as such
}

# --- Group B: legacy 7B local router --------------------------------------------------
LEGACY_7B = re.compile(r"Qwen ?2\.5|Qwen 7B|qwen-2\.5-7b", re.IGNORECASE)
LEGACY_7B_ALLOWED = HISTORICAL_FILES | {
    DOC_30,  # §0 supersession list ("Qwen 2.5 7B was the local router")
    "43_IMPERIUM_LOGIC_DETAIL.md",  # §17 historical SQL examples (annotated)
}

# --- Group C: concrete cloud model versions (superseded AND current) ------------------
# Superseded on 2026-09-17: Sonnet 4.6, Opus 4.8, Fable 5, GPT-5.5.
# Current: Sonnet 5, Opus 5, Fable 5.1, GPT-5.6 Sol, GPT-6 Astra (+ API identifiers).
# Either family may only be spelled out by the owner (doc 30 §3) or by historical docs.
CONCRETE_CLOUD = re.compile(
    r"Sonnet 4\.6|Opus 4\.8|GPT-5\.5|Fable 5\b"
    r"|Sonnet 5\b|Opus 5\b|Fable 5\.1|GPT-5\.6|GPT-6\b|\bAstra\b"
    r"|claude-sonnet-5|claude-opus-5|claude-fable-5-1|gpt-6-astra"
)
CONCRETE_CLOUD_ALLOWED = HISTORICAL_FILES | {
    DOC_30,  # §3 canonical mapping
    "56_AUTONOMOUS_CODING_ORCHESTRATOR.md",  # Codex runner pricing, not routing
    "76_ACTIVATION_ROADMAP.md",  # authoring attribution line only
    "78_TOOLBOX_CATALOG.md",  # authoring attribution + historical seed 0039 note
}

# Files where "Q5" is a question / decision identifier and must be preserved.
Q5_IDENTIFIER_FILES = (
    "75_MEMOIRE_VECTORIELLE_UNIFIEE.md",
    "76_ACTIVATION_ROADMAP.md",
    "activation_cards/VAGUE_25.md",
)

SAFEGUARD_ROLE = "high_reasoning_safeguard"

# Active docs allowed to name the safeguard role, with the function each one describes.
# Anything else naming the role is an unreviewed spread and must be justified here.
SAFEGUARD_ROLE_CONSUMERS = {
    DOC_30,  # owner (§3.8quater, §5.6, §5.7, §7.8, §9)
    "16_AI_BACKEND_LAYER_OVERVIEW.md",  # role tree
    "31_AI_TASKS_AND_RESULTS_CONTRACT.md",  # §17 thresholds mirror doc 30 §5.6
    "40_PULSE_LOGIC_DETAIL.md",  # critical mechanism cross-reference
    "52_AI_DECISION_FRAMEWORK.md",  # §8.5 explicitly says attempt 3 is NOT the safeguard
    "78_TOOLBOX_CATALOG.md",  # F1-04 router description, F3-11 role list
    "AGENTS.md",  # "when to use what" quick table
}


def _docs_files() -> list[Path]:
    files = list(DOCS_MASTER.rglob("*.md")) + list(DOCS_MASTER.rglob("*.yaml"))
    return sorted(p for p in files if p.is_file())


def _is_historical(path: Path) -> bool:
    rel = path.relative_to(DOCS_MASTER)
    return bool(HISTORICAL_DIRS & set(rel.parts[:-1]))


def _violations(pattern: re.Pattern[str], allowed_files: set[str]) -> list[str]:
    found: list[str] = []
    for path in _docs_files():
        if _is_historical(path) or path.name in allowed_files:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                found.append(f"{path.relative_to(DOCS_MASTER)}:{lineno}: {line.strip()}")
    return found


def _doc30() -> str:
    return (DOCS_MASTER / DOC_30).read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    assert start in text, start
    assert end in text, end
    return text.split(start, 1)[1].split(end, 1)[0]


@pytest.mark.parametrize(
    ("pattern", "allowed", "label"),
    [
        (STALE_LOCAL_RUNTIME, STALE_LOCAL_RUNTIME_ALLOWED, "stale local runtime/model"),
        (LEGACY_7B, LEGACY_7B_ALLOWED, "legacy 7B local router"),
        (CONCRETE_CLOUD, CONCRETE_CLOUD_ALLOWED, "concrete cloud model version"),
    ],
    ids=["stale-local-runtime", "legacy-7b", "concrete-cloud"],
)
def test_concrete_model_names_stay_in_owner_or_historical_docs(pattern, allowed, label):
    violations = _violations(pattern, allowed)
    assert violations == [], (
        f"{label} named outside doc 30 §3 / F10 / historical docs "
        f"(use the generic role instead):\n" + "\n".join(violations)
    )


def test_local_executor_concrete_model_only_in_doc30_and_f10():
    owners = {DOC_30, DOC_F10}
    violations = _violations(re.compile(re.escape("Qwen3.6-27B")), owners)
    assert violations == [], "local_executor artefact leaked outside doc 30 §3 / F10:\n" + "\n".join(
        violations
    )

    doc30 = _doc30()
    section_3_3 = _section(doc30, "### 3.3", "### 3.4")
    assert "`local_executor`" in section_3_3
    assert f"`{LOCAL_EXECUTOR_MODEL}`" in section_3_3
    assert "F10" in section_3_3  # deployment delegated to F10, not duplicated

    f10 = (DOCS_MASTER / DOC_F10).read_text(encoding="utf-8")
    assert f"`{LOCAL_EXECUTOR_MODEL}`" in f10
    assert "§3" in f10 and DOC_30 in f10  # F10 points back to the logical owner


def test_doc30_carries_no_obsolete_local_runtime_language():
    doc30 = _doc30()
    for line in doc30.splitlines():
        assert not STALE_LOCAL_RUNTIME.search(line), line
        assert not re.search(r"\bQ5\b", line), line


def test_f10_does_not_claim_the_logical_mapping():
    f10 = (DOCS_MASTER / DOC_F10).read_text(encoding="utf-8")
    # F10 documents the deployed artefact but must not restate the cloud tier mapping.
    assert not CONCRETE_CLOUD.search(f10)
    assert SAFEGUARD_ROLE not in f10  # a logical role, nothing physical to deploy
    assert "appartient exclusivement" in f10 and DOC_30 in f10


def test_q5_question_identifiers_are_preserved():
    for rel in Q5_IDENTIFIER_FILES:
        text = (DOCS_MASTER / rel).read_text(encoding="utf-8")
        assert re.search(r"\bQ5\b", text), f"Q5 question/decision identifier lost in {rel}"


def test_flags_stay_off_in_ownership_docs():
    for rel in (DOC_30, DOC_F10, "activation_cards/VAGUE_6.md"):
        text = (DOCS_MASTER / rel).read_text(encoding="utf-8")
        assert "qwen_enabled=False" in text, rel
        assert "real_ai_enabled=False" in text, rel


# --- 2026-09-17 mapping update ---------------------------------------------------------

SUBSECTION_BOUNDS = {
    "local_executor": ("### 3.3", "### 3.4"),
    "first_cloud_tier": ("### 3.5", "### 3.6"),
    "high_reasoning": ("### 3.6", "### 3.7"),
    "sustained_long_context": ("### 3.7", "### 3.8 "),
    "health_specialist": ("### 3.8 ", "### 3.8bis"),
    "finance_specialist": ("### 3.8bis", "### 3.8ter"),
    "web_fresh_data": ("### 3.8ter", "### 3.8quater"),
    "high_reasoning_safeguard": ("### 3.8quater", "### 3.9"),
}


@pytest.mark.parametrize("role", sorted(CANONICAL_MAPPING))
def test_doc30_section_3_states_the_canonical_mapping(role):
    model, api_id = CANONICAL_MAPPING[role]
    doc30 = _doc30()
    section = _section(doc30, *SUBSECTION_BOUNDS[role])
    assert f"`{role}`" in section, f"{role} subsection does not name its role"
    current_line = next(
        (line for line in section.splitlines() if line.startswith("- Current model:")),
        "",
    )
    assert model in current_line, f"{role}: expected {model!r} in {current_line!r}"
    if api_id:
        assert f"`{api_id}`" in current_line, f"{role}: API identifier {api_id} missing"

    # The summary table at the top of §3 must agree with the subsection.
    table = _section(doc30, "Current logical mapping (summary", "### 3.1")
    row = next((line for line in table.splitlines() if f"| `{role}` |" in line), "")
    assert model in row, f"{role}: §3 summary row disagrees with subsection: {row!r}"


def test_doc30_superseded_versions_only_as_history():
    """Old assignments survive only as dated 'previous assignment' / supersession notes."""
    doc30 = _doc30()
    old = re.compile(r"Sonnet 4\.6|Opus 4\.8|GPT-5\.5|Fable 5\b(?!\.1)")
    history_markers = (
        "superseded",  # §0 note and "Previous assignment: … (superseded 2026-09-17)"
        "was suspended",  # §3.7 dated availability history
        "The role was served by Fable 5 again",  # §3.7 dated availability history
    )
    for lineno, line in enumerate(doc30.splitlines(), 1):
        if not old.search(line):
            continue
        assert any(marker in line for marker in history_markers), (
            f"doc 30:{lineno} names a superseded model outside a historical note: {line.strip()}"
        )
        if line.startswith("- Current model:"):
            assert "Previous assignment" in line, line


def test_doc30_safeguard_role_owns_independent_rescoring():
    doc30 = _doc30()
    quater = _section(doc30, "### 3.8quater", "### 3.9")
    assert f"`{SAFEGUARD_ROLE}`" in quater
    assert "GPT-6 Astra" in quater and "`gpt-6-astra`" in quater
    # Independence criterion and the explicit distinction from the Fable-native safeguard.
    assert "independent" in quater.lower()
    assert "not** the Anthropic-native content safeguard" in quater

    critical = _section(doc30, "#### Critical tier (180–200)", "### 5.7")
    step1 = _section(critical, "**Step 1", "**Step 2")
    assert f"`{SAFEGUARD_ROLE}`" in step1
    assert "§3.8ter" not in step1.split("(Until 2026-09-17")[0]
    assert "below 180" in step1 and "confirms ≥180" in step1
    step2 = _section(critical, "**Step 2", "**Anti-loop breaker")
    assert "high_reasoning remains the final orchestrator" in step2
    assert "sustained_long_context" in step2 and SAFEGUARD_ROLE in step2
    breaker = critical.split("**Anti-loop breaker", 1)[1]
    assert "high_reasoning must produce the final answer itself" in breaker

    # §3.8ter no longer carries the verification overload.
    ter = _section(doc30, "### 3.8ter", "### 3.8quater")
    assert "independent critical re-scoring" not in ter.split("Former overloads")[0]


def test_native_fable_safeguard_is_not_relabelled_as_the_role():
    doc30 = _doc30()
    s37 = _section(doc30, "### 3.7", "### 3.8 ")
    assert "Anthropic-native mechanism" in s37
    assert "Anthropic mechanism, not an Imperium role" in s37
    s78 = _section(doc30, "### 7.8", "### 7.9")
    assert "provider-native content safeguard" in s78
    assert f"not the Imperium role `{SAFEGUARD_ROLE}`" in s78

    # Consumers describing the WR native reroute must keep the native wording.
    wr = (DOCS_MASTER / "32_WR_INTERACTIVE_WORKFLOW.md").read_text(encoding="utf-8")
    assert "safeguard reroutes high-risk topics to the high reasoning model" in wr
    assert SAFEGUARD_ROLE not in wr


def test_safeguard_role_consumers_are_reviewed_and_no_stale_rescorer_remains():
    users: set[str] = set()
    stale: list[str] = []
    stale_rescorer = re.compile(
        r"health specialist re-score|independent verification model \(§3\.8ter\)"
        r"|re-score indépendant \(doc 30 §3\.8ter\)|independent fallback model \(doc 30 §3\.8ter\)"
    )
    for path in _docs_files():
        if _is_historical(path) or path.name in HISTORICAL_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        if SAFEGUARD_ROLE in text:
            users.add(path.name)
        for lineno, line in enumerate(text.splitlines(), 1):
            if stale_rescorer.search(line):
                stale.append(f"{path.relative_to(DOCS_MASTER)}:{lineno}: {line.strip()}")
    assert stale == [], "stale §5.6 re-scorer attribution:\n" + "\n".join(stale)
    assert users == SAFEGUARD_ROLE_CONSUMERS, (
        f"unreviewed spread of {SAFEGUARD_ROLE}: "
        f"unexpected={sorted(users - SAFEGUARD_ROLE_CONSUMERS)} "
        f"missing={sorted(SAFEGUARD_ROLE_CONSUMERS - users)}"
    )


def test_doc52_last_resort_generation_is_not_the_safeguard():
    doc52 = (DOCS_MASTER / "52_AI_DECISION_FRAMEWORK.md").read_text(encoding="utf-8")
    loop = _section(doc52, "### 8.5 The fallback loop", "### 8.6")
    assert f"**not** `{SAFEGUARD_ROLE}`" in loop
    assert "ATTEMPT 3 — last-resort generator (sustained_long_context, doc 30 §3.7)" in loop
    assert "§3.8ter) takes over" not in loop


def test_role_lists_include_the_safeguard_role():
    for rel, marker in (
        (DOC_30, "high_reasoning_safeguard → independent contradictory verification"),
        ("16_AI_BACKEND_LAYER_OVERVIEW.md", "├─ high_reasoning_safeguard"),
        ("AGENTS.md", "→ high_reasoning_safeguard (doc 30 §5.6)"),
    ):
        text = (DOCS_MASTER / rel).read_text(encoding="utf-8")
        assert marker in text, rel
