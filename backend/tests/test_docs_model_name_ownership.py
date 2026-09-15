"""Documentary ownership invariant for concrete AI model names in docs_master.

Rule (doc 30 §0 / §3, F10 header):
- doc 30 §3 is the ONLY owner of the logical ROLE -> concrete model/version mapping;
- F10 owns the physical/technical local deployment only (GPU, GGUF, quant, runtime…);
- every other spec names generic roles (local_executor, first_cloud_tier, …).

Same family of repo invariant as `test_toolbox_roles_dv6.py` (grep-style, hermetic,
pure file reading): historical audits / applied patches / SQL examples may keep the
old names for traceability, everything else must stay role-based.
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

# --- Group C: concrete cloud model versions -------------------------------------------
CONCRETE_CLOUD = re.compile(r"Sonnet 4\.6|Opus 4\.8|GPT-5\.5|Fable 5\b")
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

    doc30 = (DOCS_MASTER / DOC_30).read_text(encoding="utf-8")
    section_3_3 = doc30.split("### 3.3", 1)[1].split("### 3.4", 1)[0]
    assert "`local_executor`" in section_3_3
    assert f"`{LOCAL_EXECUTOR_MODEL}`" in section_3_3
    assert "F10" in section_3_3  # deployment delegated to F10, not duplicated

    f10 = (DOCS_MASTER / DOC_F10).read_text(encoding="utf-8")
    assert f"`{LOCAL_EXECUTOR_MODEL}`" in f10
    assert "§3" in f10 and DOC_30 in f10  # F10 points back to the logical owner


def test_doc30_carries_no_obsolete_local_runtime_language():
    doc30 = (DOCS_MASTER / DOC_30).read_text(encoding="utf-8")
    for line in doc30.splitlines():
        assert not STALE_LOCAL_RUNTIME.search(line), line
        assert not re.search(r"\bQ5\b", line), line


def test_f10_does_not_claim_the_logical_mapping():
    f10 = (DOCS_MASTER / DOC_F10).read_text(encoding="utf-8")
    # F10 documents the deployed artefact but must not restate the cloud tier mapping.
    assert not CONCRETE_CLOUD.search(f10)
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
