"""Export documentaire Vector, sans démarrer l'application ni accéder à la base."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi import FastAPI  # noqa: E402

from app.api.v1.router import api_router  # noqa: E402
from pydantic import BaseModel
from app.schemas import rides

NAME = "Vector_Frontend_Kit"
SOURCE_NAMES = (
    "13_VECTOR_MVP_PHASE_DECISION.md",
    "33_VECTOR_LOGIC_DETAIL.md",
    "39_WRS_VECTOR_LEARNING_LOOP.md",
    "46_VECTOR_FUEL_SMART_TRACKING.md",
    "55_VECTOR_HUD_FINAL_INTERFACE.md",
    "59_DESIGN_SYSTEM_V1_DRAFT.md",
    "57_VECTOR_RIDE_SCORING_ML.md",
    "58_DOC_57_INTEGRATION_PATCHES.md",
)
METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
MODELS = {name: model for name, model in vars(rides).items()
          if isinstance(model, type) and issubclass(model, BaseModel)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_documents(source: Path, destination: Path) -> None:
    """Seuls des documents Markdown réguliers sont admis, sans suivi de symlink."""
    if source.is_symlink():
        raise ValueError("Le dossier source ne doit pas être un lien symbolique.")
    files = sorted(source.iterdir())
    if any(p.is_symlink() or not p.is_file() or p.suffix != ".md" for p in files):
        raise ValueError("Le dossier documentaire contient un fichier inattendu.")
    destination.mkdir(parents=True, exist_ok=True)
    for path in files:
        shutil.copyfile(path, destination / path.name)


def export_contract() -> dict:
    app = FastAPI(title="Vector — contrat frontend", version="checkout-export")
    app.include_router(api_router, prefix="/api")
    full = app.openapi()
    prefixes = ("/api/imperium/vector/", "/api/auth/")
    paths = {path: value for path, value in full["paths"].items() if path.startswith(prefixes)}
    # Fermeture transitive des références : pas de schémas de domaines non utilisés.
    components: dict[str, dict] = {}

    def resolve(value: Any) -> None:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if ref:
                _, category, name = ref.removeprefix("#/").split("/")
                group = components.setdefault(category, {})
                if name not in group:
                    group[name] = full["components"][category][name]
                    resolve(group[name])
            for child in value.values():
                resolve(child)
        elif isinstance(value, list):
            for child in value:
                resolve(child)

    resolve(paths)
    if "securitySchemes" in full.get("components", {}):
        components["securitySchemes"] = full["components"]["securitySchemes"]
    return {
        "openapi": full["openapi"],
        "info": full["info"],
        "paths": paths,
        "components": components,
    }


def write_contract_guides(folder: Path, schema: dict) -> None:
    endpoints = [
        "# Routes extraites du code\n",
        "Les erreurs métier et uploads bruts complètent OpenAPI : lire le document 05.",
        "Un header déclaré ne prouve pas à lui seul la déduplication du handler.\n",
    ]
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method not in METHODS:
                continue
            params = operation.get("parameters", [])
            idempotency = any(p["name"].lower() == "idempotency-key" for p in params)
            endpoints.extend([
                f"## {method.upper()} {path}\n",
                operation.get("summary", ""),
                operation.get("description", ""),
                f"\nIdempotency-Key déclaré : {'oui' if idempotency else 'non'}.",
                f"Réponses déclarées : {', '.join(operation['responses'])}.\n",
            ])
            for p in params:
                endpoints.append(
                    f"- `{p['name']}` ({p['in']}, "
                    f"{'requis' if p.get('required') else 'facultatif'}) : "
                    f"`{json.dumps(p.get('schema', {}), ensure_ascii=False)}`"
                )
            if "requestBody" in operation:
                endpoints.append(
                    "\nCorps :\n```json\n"
                    + json.dumps(operation["requestBody"], ensure_ascii=False, indent=2)
                    + "\n```\n"
                )
    (folder / "endpoints.md").write_text("\n".join(endpoints), encoding="utf-8")
    forms = [
        "# Champs et contraintes des modèles\n",
        "Extrait automatique des modèles référencés. Les validateurs métier peuvent "
        "ajouter des contraintes ; voir les parcours et exemples validés.\n",
    ]
    for name, model in sorted(schema["components"].get("schemas", {}).items()):
        forms.append(f"## {name}\n")
        if model.get("description"):
            forms.append(model["description"] + "\n")
        required = model.get("required", [])
        for key, value in model.get("properties", {}).items():
            forms.append(
                f"- **{key}** — {'requis' if key in required else 'facultatif'} : "
                f"`{json.dumps(value, ensure_ascii=False)}`"
            )
        forms.append("")
    (folder / "forms.md").write_text("\n".join(forms), encoding="utf-8")


PREFIX = "/api/imperium/vector"
SESSION_ID = "00000000-0000-4000-8000-000000000001"
OFFER_ID = "00000000-0000-4000-8000-000000000002"
RECO_ID = "00000000-0000-4000-8000-000000000003"
AT = "2026-10-22T18:00:00+02:00"


def example(method: str, path: str, schema: str, body: dict) -> dict:
    validated = MODELS[schema].model_validate(body)
    return {"synthetic": True, "method": method, "path": PREFIX + path,
            "schema": schema, "body": validated.model_dump(mode="json", exclude_unset=True)}


def request_examples() -> list[dict]:
    """Exemples fictifs, validés par les vrais DTO, jamais envoyés au backend."""
    rows = [
        ("POST", "/sessions", "SessionStart", {"target_ca_cents": 20000}),
        ("POST", "/sessions", "SessionStart", {}),
        ("PATCH", "/sessions/{session_id}", "SessionUpdate",
         {"version": 1, "strategic_direction": "Paris centre"}),
        ("POST", "/sessions/{session_id}/manual-revenue", "ManualRevenueCreate",
         {"amount_cents": 1250, "zone": "Bercy", "occurred_at": AT, "wallet": "cash"}),
        ("POST", "/sessions/{session_id}/manual-expense", "ManualExpenseCreate",
         {"amount_cents": 500, "category": "peage", "occurred_at": AT}),
        ("POST", "/sessions/{session_id}/drop-zone", "DropZoneCreate",
         {"zone": "Bercy", "latitude": "48.838000", "longitude": "2.380000",
          "gps_confidence": "0.80", "real_duration_minutes": 25}),
        ("POST", "/sessions/{session_id}/complete", "SessionComplete",
         {"review_note": "Session de démonstration"}),
        ("POST", "/recommendations", "RecommendationRequest", {"current_zone": "Bercy"}),
        ("POST", "/recommendations/{recommendation_id}/feedback", "RecommendationFeedback",
         {"useful": True, "ride_user_action": "accepted"}),
        ("POST", "/sessions/{session_id}/offers", "RideOfferCreate",
         {"price_cents": 1800, "platform": "bolt", "estimated_duration_min": 20,
          "approach_duration_min": 5, "destination_zone_code": "75012"}),
        ("POST", "/offers/{offer_id}/decision", "RideDecisionRequest",
         {"version": 1, "decision": "accepted"}),
        ("POST", "/offers/{offer_id}/outcome", "RideOutcomeRequest",
         {"version": 2, "actual_earning_cents": 1800, "approach_minutes": 5,
          "wait_minutes": 2, "ride_minutes": 20, "return_minutes": 3, "record_revenue": True}),
        ("PATCH", "/rules/{rule_code}", "BusinessRuleUpdate",
         {"version": 1, "reason": "Révision validée par le chauffeur", "is_active": False}),
    ]
    return [example(*row) for row in rows]


def response_examples() -> list[dict]:
    session = {
        "id": SESSION_ID, "status": "active", "started_at": AT, "ended_at": None,
        "target_ca_cents": 20000, "strategic_direction": None, "mission_id": None,
        "review_note": None, "version": 1,
        "kpis": {"revenue_cents": 1250, "expense_cents": 500, "net_cents": 750,
                 "revenue_entries": 1, "expense_entries": 1, "drop_zones": 1,
                 "elapsed_minutes": 60, "target_progress": "0.0625", "objective_reached": False},
    }
    recommendation = {
        "id": RECO_ID, "session_id": SESSION_ID, "requested_at": AT,
        "current_zone": "Bercy", "recommendation": "abstain", "zone": None,
        "reason": "Haute incertitude, à toi de juger.", "confidence": "0",
        "hourly_rate_estimate_cents": None, "slot": "semaine, 17 h–19 h",
        "zones": [], "missing_context": ["events", "trains", "airports", "traffic"],
        "feedback_useful": None, "ride_user_action": None,
        "feedback_reason": None, "feedback_at": None,
    }
    offer = {
        "id": OFFER_ID, "session_id": SESSION_ID, "offered_at": AT,
        "source": "manual", "platform": "bolt", "price_cents": 1800,
        "distance_km": None, "estimated_duration_min": 20, "approach_distance_km": None,
        "approach_duration_min": 5, "surge_multiplier": None, "pickup_zone": None,
        "destination_zone": "Bercy", "payment_type": "card", "ride_type": "immediate",
        "features": {}, "decision": None, "decided_at": None, "decision_note": None,
        "actual_earning_cents": None, "mobilized_minutes": None,
        "actual_hourly_rate_cents": None, "revenue_transaction_id": None,
        "pickup_zone_code": None, "destination_zone_code": "75012", "version": 1,
        "signal": None, "signal_source": "rules_only", "signal_reason": None,
        "triggered_rules": [],
    }
    drop = {"id": "00000000-0000-4000-8000-000000000004", "zone": "Bercy",
            "latitude": "48.838000", "longitude": "2.380000", "gps_confidence": "0.80",
            "real_duration_minutes": 25, "recorded_at": AT}
    rule = {"rule_code": "R1", "name": "Éviter le 8e", "description": "Exemple fictif",
            "conditions": {"zone_codes": ["75008"], "applies_to": ["destination"]},
            "action": "red", "is_active": True, "is_hard_rule": True,
            "times_applied": 0, "revision_count": 0, "version": 1, "last_revised_at": None}
    rows = [
        ("GET", "/sessions/current", "CurrentSessionRead", {"session": None}),
        ("GET", "/sessions/current", "CurrentSessionRead", {"session": session}),
        ("GET", "/sessions/{session_id}", "SessionRead", session),
        ("GET", "/sessions", "SessionListResponse", {"items": [session]}),
        ("POST", "/sessions/{session_id}/manual-revenue", "SessionEntryResult",
         {"transaction_id": "00000000-0000-4000-8000-000000000005", "session": session}),
        ("POST", "/sessions/{session_id}/drop-zone", "DropZoneRead", drop),
        ("GET", "/recommendations/latest", "RecommendationRead", recommendation),
        ("GET", "/offers/{offer_id}", "RideOfferRead", offer),
        ("GET", "/sessions/{session_id}/offers", "RideOfferListResponse", {"items": [offer]}),
        ("GET", "/rules", "BusinessRuleListResponse", {"items": [rule], "not_coded": ["R3", "R4", "R9"]}),
        ("GET", "/training-summary", "TrainingSummaryRead",
         {"offers": 0, "decided": 0, "accepted": 0, "refused": 0, "missed": 0,
          "with_outcome": 0, "median_hourly_rate_cents": None, "phase": "cold_start",
          "message": "Collecte en cours ; modèle non entraîné."}),
    ]
    return [example(*row) for row in rows]


def ui_scenarios() -> dict:
    screens = [
        ("Dashboard", "Aucune session", "Démarrer ou reprendre la session"),
        ("Démarrage", "Cible facultative", "Confirmer puis attendre le serveur"),
        ("Session active", "Pas de conseil récent", "KPIs serveur et où aller"),
        ("Gain manuel", "Montant requis", "Une écriture Vault via Vector"),
        ("Dépense", "Montant et catégorie requis", "Une écriture Vault via Vector"),
        ("Capture", "Envoi non raccordé", "Brouillon local et saisie manuelle"),
        ("Où aller ?", "Aucun historique suffisant", "Abstention explicite"),
        ("Conseil", "Conseil introuvable", "Zone, raison, date, contexte manquant"),
        ("Retour", "Aucun retour", "Utile ou non, décision réelle"),
        ("Dépose", "Zone requise", "Confirmation explicite"),
        ("Bilan", "Pas de session close", "Clôture puis replan distinct"),
    ]
    return {
        "synthetic": True,
        "shared_states": {
            "loading": "Chargement indépendant par section",
            "empty": "Aucune donnée, pas de zéro fictif",
            "error": "Erreur réelle, brouillon conservé",
            "offline": "Cache daté et écritures en attente",
            "conflict": "État serveur et saisie locale comparables",
            "disabled": "Capacité non raccordée explicitement annoncée",
            "stale": "Date originale conservée ; aucun halo live",
            "pending": "Brouillon persistant", "syncing": "Envoi en cours",
        },
        "screens": [{"screen": f"VEC-{i:02}", "title": title, "empty": empty, "content": content}
                    for i, (title, empty, content) in enumerate(screens, 1)],
        "path_parameters": {"session_id": SESSION_ID, "offer_id": OFFER_ID,
                            "recommendation_id": RECO_ID, "rule_code": "R1"},
        "notes": "Les exemples sont des snapshots indépendants, pas un ledger cumulatif. Aucun envoi automatique.",
    }


def build(output: Path) -> Path:
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    final_folder, archive = output / NAME, output / f"{NAME}.zip"
    if final_folder.exists() or archive.exists():
        raise FileExistsError("Cette livraison existe déjà ; choisir un nouveau dossier.")
    with tempfile.TemporaryDirectory(prefix=".vector-build-", dir=output) as temporary:
        folder = Path(temporary) / NAME
        copy_documents(ROOT / "deliveries/vector_frontend", folder)
        source_files = [ROOT / "docs_master" / name for name in SOURCE_NAMES]
        for source in source_files:
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"Source documentaire non régulière : {source.name}")
            destination = folder / "sources" / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.name == "55_VECTOR_HUD_FINAL_INTERFACE.md":
                content = source.read_text(encoding="utf-8")
                content = "\n".join(line for line in content.splitlines() if "shaker" not in line.lower()) + "\n"
                destination.write_text(
                    "> Annexe adaptée au périmètre demandé. Les documents 01–12 arbitrent les écarts historiques.\n\n" + content,
                    encoding="utf-8",
                )
            elif source.name == "59_DESIGN_SYSTEM_V1_DRAFT.md":
                content = source.read_text(encoding="utf-8")
                content = content.split("## 14. VECTOR SCREEN ARCHITECTURE MAPPING V1", 1)[1].split("## 15. PULSE SCREEN ARCHITECTURE MAPPING V1", 1)[0]
                destination.with_name("59_VECTOR_SCREEN_EXTRACT.md").write_text(
                    "# Extrait historique du doc 59 — section 14 Vector\n\n"
                    "> Pour les routes, halos et capacités réelles, appliquer les arbitrages du document 11.\n\n" + content,
                    encoding="utf-8",
                )
            else:
                shutil.copyfile(source, destination)
        schema = export_contract()
        write_json(folder / "contracts/openapi.json", schema)
        write_contract_guides(folder / "contracts", schema)
        write_json(folder / "examples/requests.json", request_examples())
        write_json(folder / "examples/responses.json", response_examples())
        write_json(folder / "examples/ui_scenarios.json", ui_scenarios())
        # Scripts et tests rendent la méthode d'export vérifiable depuis le dépôt.
        for relative in (
            "scripts/build_vector_frontend_kit.py", "scripts/serve_vector_frontend_kit.py",
            "backend/tests/test_vector_frontend_kit.py",
        ):
            destination = folder / "tooling" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        selected = [
            "deliveries/vector_frontend", "backend/app", "scripts/build_vector_frontend_kit.py",
            "scripts/serve_vector_frontend_kit.py", "backend/tests/test_vector_frontend_kit.py",
            *(str(path.relative_to(ROOT)) for path in source_files),
        ]
        git = lambda *args: subprocess.check_output(
            ["git", "-C", str(ROOT), *args], text=True
        ).strip()
        payloads = sorted(path for path in folder.rglob("*") if path.is_file())
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "reference_commit": git("rev-parse", "HEAD"),
            "selected_source_status": git("status", "--porcelain", "--", *selected),
            "synthetic_examples_only": True,
            "source_fingerprints": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files + [ROOT / "backend/app/schemas/rides.py", ROOT / "backend/app/api/v1/routes/imperium_vector.py"]},
            "operation_count": sum(
                method in METHODS for ops in schema["paths"].values() for method in ops
            ),
            "files": {
                str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in payloads
            },
        }
        write_json(folder / "manifest.json", manifest)
        staged_archive = Path(temporary) / archive.name
        with zipfile.ZipFile(staged_archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    zipped.write(path, f"{NAME}/{path.relative_to(folder)}")
        folder.rename(final_folder)
        staged_archive.rename(archive)
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.output))


if __name__ == "__main__":
    main()
