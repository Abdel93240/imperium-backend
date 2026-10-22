"""Export documentaire Pulse, sans démarrer l'application ni accéder à la base."""

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
from app.schemas import (  # noqa: E402
    pulse,
    pulse_health,
    pulse_hydration,
    pulse_meals,
    pulse_signals,
    pulse_training,
    pulse_workouts,
)

NAME = "Pulse_Frontend_Kit"
SOURCE_NAMES = (
    "07_ANDROID_APP_RESPONSIBILITIES.md",
    "08_NON_NEGOTIABLE_RULES.md",
    "14_OFFLINE_CLIENT_AUTHORITY.md",
    "30_AI_ROUTING_AND_SCORING_POLICY.md",
    "34_PULSE_MEDICAL_FEED_AI.md",
    "40_PULSE_LOGIC_DETAIL.md",
    "59_DESIGN_SYSTEM_V1_DRAFT.md",
    "63_FRONTEND_ARCHITECTURE_V1.md",
    "79_FRONTEND_MAP.md",
)
METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
REQUEST_MODELS = {
    model.__name__: model
    for model in (
        pulse.PulseEntryCreate,
        pulse.FoodStockItemCreate,
        pulse.FoodStockItemUpdate,
        pulse.StockDeclarationPreviewRequest,
        pulse.StockDeclarationCreate,
        pulse.PantryScanValidateRequest,
        pulse_meals.MealDraftCreate,
        pulse_meals.MealConfirmRequest,
        pulse_hydration.HydrationLogCreate,
        pulse_workouts.WorkoutCreate,
        pulse_workouts.WorkoutUpdate,
        pulse_workouts.WorkoutStartRequest,
        pulse_workouts.WorkoutCompleteRequest,
        pulse_workouts.WorkoutSkipRequest,
        pulse_workouts.EquipmentCreate,
        pulse_health.ConsentGrantRequest,
        pulse_health.BodySnapshotCreate,
        pulse_health.PainLogCreate,
        pulse_health.MedicalRuleCreate,
        pulse_health.MedicalRuleActivateRequest,
        pulse_health.RedFlagResolveRequest,
        pulse_signals.SubjectiveReportCreate,
        pulse_signals.ProposalDecisionRequest,
        pulse_signals.DispatchReactionRequest,
        pulse_training.ProgramCreate,
        pulse_training.ProgramStatusRequest,
        pulse_training.TargetsReplace,
    )
}


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
    app = FastAPI(title="Pulse — contrat frontend", version="checkout-export")
    app.include_router(api_router, prefix="/api")
    full = app.openapi()
    prefixes = ("/api/imperium/pulse/", "/api/auth/", "/api/ai/knowledge-inbox")
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


def request_examples() -> list[dict]:
    """Saisies fictives ; aucune fixture n'est extraite de données personnelles."""
    at = "2026-10-20T12:00:00+02:00"
    rows = [
        ("POST", "/entries", "PulseEntryCreate",
         {"entry_date": "2026-10-20", "sleep_hours": "7.50", "energy_level": 6}),
        ("POST", "/food-stock", "FoodStockItemCreate",
         {"name": "Riz", "quantity": "1.000", "unit": "kg"}),
        ("PATCH", "/food-stock/{item_id}", "FoodStockItemUpdate",
         {"version": 1, "quantity": "0.800"}),
        ("POST", "/food-stock/declarations/preview", "StockDeclarationPreviewRequest",
         {"text": "2 kg de riz et 6 œufs"}),
        ("POST", "/food-stock/declarations", "StockDeclarationCreate",
         {"lines": [{"name": "Riz", "quantity": "2", "unit": "kg"}]}),
        ("POST", "/food-stock/scans/{scan_id}/validate", "PantryScanValidateRequest",
         {"lines": [{"action": "add", "name": "Riz", "quantity": "1", "unit": "kg"}]}),
        ("POST", "/meals/drafts", "MealDraftCreate",
         {"description": "200 g de riz", "source": "text", "eaten_at": at}),
        ("POST", "/meals/{meal_id}/confirm", "MealConfirmRequest",
         {"label": "Repas de démonstration", "stock_lines": []}),
        ("POST", "/hydration-logs", "HydrationLogCreate",
         {"amount_ml": 250, "decrement_stock": False}),
        ("POST", "/workouts", "WorkoutCreate",
         {"title": "Séance de démonstration", "planned_at": at, "duration_minutes": 20,
          "exercises": [{"name": "Exercice personnel", "sets": 2, "reps": 8}]}),
        ("PATCH", "/workouts/{workout_id}", "WorkoutUpdate",
         {"version": 1, "duration_minutes": 15}),
        ("POST", "/workouts/{workout_id}/start", "WorkoutStartRequest", {}),
        ("POST", "/workouts/{workout_id}/complete", "WorkoutCompleteRequest",
         {"duration_minutes": 15, "intensity_score": 4,
          "results": [{"index": 0, "done_sets": 2, "done_reps": [8, 8]}]}),
        ("POST", "/workouts/{workout_id}/skip", "WorkoutSkipRequest",
         {"reason": "Imprévu professionnel"}),
        ("POST", "/equipment", "EquipmentCreate", {"name": "Tapis"}),
        ("POST", "/consents/{domain}", "ConsentGrantRequest",
         {"text_version": "REPRENDRE_VERSION_LUE"}),
        ("POST", "/body-snapshots", "BodySnapshotCreate",
         {"measured_at": at, "weight_kg": "80.00"}),
        ("POST", "/pain-logs", "PainLogCreate",
         {"body_zone": "knee", "side": "left", "severity": 2}),
        ("POST", "/medical-rules", "MedicalRuleCreate",
         {"rule_type": "workout_limit", "rule_text": "Exemple fictif à remplacer après relecture.",
          "severity": "info"}),
        ("POST", "/medical-rules/{rule_id}/activate", "MedicalRuleActivateRequest",
         {"reviewed_source": True, "confirmed_text": True, "still_relevant": True}),
        ("POST", "/red-flags/{flag_id}/resolve", "RedFlagResolveRequest",
         {"resolution": "dismissed_with_reason", "reason": "Exemple de recette uniquement"}),
        ("POST", "/reports", "SubjectiveReportCreate", {"kind": "fatigue", "level": 2}),
        ("POST", "/proposals/{proposal_id}/decision", "ProposalDecisionRequest",
         {"decision": "refused", "user_explanation": "Horaire incompatible"}),
        ("POST", "/sentinel/dispatches/{dispatch_id}/reaction", "DispatchReactionRequest",
         {"reaction": "useful"}),
        ("POST", "/programs", "ProgramCreate",
         {"name": "Programme de démonstration",
          "mesocycle": {"phase": "accumulation", "week_current": 1, "weeks_total": 4}}),
        ("POST", "/programs/{program_id}/status", "ProgramStatusRequest", {"status": "paused"}),
        ("PUT", "/programs/{program_id}/targets", "TargetsReplace",
         {"week_start": "2026-10-19",
          "targets": [{"muscle_group": "legs", "target_sets": 6, "tolerance_sets": 2}]}),
    ]
    examples = []
    for method, suffix, name, body in rows:
        REQUEST_MODELS[name].model_validate(body)
        examples.append({
            "synthetic": True, "method": method, "path": "/api/imperium/pulse" + suffix,
            "schema": name, "body": body,
        })
    return examples


def ui_scenarios() -> dict:
    screens = [
        ("Aujourd'hui", "Aucune saisie", "Totaux confirmés, score absent"),
        ("Ajouter un repas", "Formulaire vierge", "Description saisie ; pas encore confirmée"),
        ("Confirmer le repas", "Brouillon introuvable", "Macros inconnues, stock décoché"),
        ("Boire", "Aucun log", "250 ml enregistrés ; objectif absent"),
        ("Planifier une séance", "Formulaire vierge", "Séance avec exercices et horaire"),
        ("Séance en cours", "Aucune séance", "Résultats locaux en attente de fin"),
        ("Adaptation", "Aucune proposition", "Proposition présentée, décision attendue"),
        ("Mesures", "Consentement ou relevés absents", "Deux relevés numériques fictifs"),
        ("Douleurs", "Aucune douleur", "Douleur ouverte, action explicite de résolution"),
        ("Repas", "Aucun repas confirmé", "Repas sans macros, total incomplet"),
        ("Sport", "Aucune séance ni programme", "Séance planifiée, programme facultatif"),
        ("Stock", "Stock vide", "Lignes avec DLC, DDM et date inconnue"),
        ("Scanner", "Aucune image choisie", "Diff proposé, quantités à confirmer"),
        ("Santé", "Consentement absent", "Document importé, analyse non disponible"),
    ]
    return {
        "synthetic": True,
        "note": "Scénarios de présentation, pas des réponses API. Valeurs fictives.",
        "shared_states": {
            "loading": "Squelette et libellé Chargement ; aucune valeur fictive.",
            "empty": "Texte contextualisé et action disponible.",
            "error": "Erreur lisible, brouillon préservé, réessayer si approprié.",
            "offline": "Dernière synchronisation affichée ; saisie en attente.",
            "syncing": "Envoi en cours ; pas de succès anticipé.",
            "conflict": "Relecture serveur et comparaison avec la saisie.",
            "disabled": "Fonction non activée ; aucune tentative d'activation client.",
            "consent_required": "Lire et accepter le texte versionné du domaine.",
        },
        "screens": [
            {"screen": f"PUL-{i:02}", "title": title, "empty": empty, "content": content}
            for i, (title, empty, content) in enumerate(screens, 1)
        ],
    }


def build(output: Path) -> Path:
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    final_folder, archive = output / NAME, output / f"{NAME}.zip"
    if final_folder.exists() or archive.exists():
        raise FileExistsError("Cette livraison existe déjà ; choisir un nouveau dossier.")
    with tempfile.TemporaryDirectory(prefix=".pulse-build-", dir=output) as temporary:
        folder = Path(temporary) / NAME
        copy_documents(ROOT / "deliveries/pulse_frontend", folder)
        source_files = [ROOT / "docs_master" / name for name in SOURCE_NAMES]
        source_files.append(ROOT / "specs/PULSE_INTELLIGENCE_LAYER_SPEC_V1.md")
        for source in source_files:
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"Source documentaire non régulière : {source.name}")
            destination = folder / "sources" / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        schema = export_contract()
        write_json(folder / "contracts/openapi.json", schema)
        write_contract_guides(folder / "contracts", schema)
        write_json(folder / "examples/requests.json", request_examples())
        write_json(folder / "examples/ui_scenarios.json", ui_scenarios())
        # Scripts et tests rendent la méthode d'export vérifiable depuis le dépôt.
        for relative in (
            "scripts/build_pulse_frontend_kit.py", "scripts/serve_pulse_frontend_kit.py",
            "backend/tests/test_pulse_frontend_kit.py",
        ):
            destination = folder / "tooling" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        selected = [
            "deliveries/pulse_frontend", "backend/app", "scripts/build_pulse_frontend_kit.py",
            "scripts/serve_pulse_frontend_kit.py", "backend/tests/test_pulse_frontend_kit.py",
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
