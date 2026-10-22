"""Export documentaire Vault, sans démarrer l'application ni accéder à la base."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess  # nosec B404
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
from app.schemas import vault, imperium

NAME = "Vault_Frontend_Kit"
SOURCE_NAMES = (
    "00_VISION_GLOBALE.md", "07_ANDROID_APP_RESPONSIBILITIES.md",
    "08_NON_NEGOTIABLE_RULES.md", "11_FINANCIAL_PRESSURE_FORMULA.md",
    "14_OFFLINE_CLIENT_AUTHORITY.md", "27_VAULT_TRANSACTIONS_WORKFLOW.md",
    "30_AI_ROUTING_AND_SCORING_POLICY.md", "37_VISION_OCR_PROMPTS.md",
    "42_VAULT_LOGIC_DETAIL.md", "59_DESIGN_SYSTEM_V1_DRAFT.md",
    "63_FRONTEND_ARCHITECTURE_V1.md",
)
METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
MODELS = {name: model for module in (vault, imperium) for name, model in vars(module).items()
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
    app = FastAPI(title="Vault — contrat frontend", version="checkout-export")
    app.include_router(api_router, prefix="/api")
    full = app.openapi()
    prefixes = ("/api/imperium/vault/", "/api/vault/", "/api/auth/")
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


ID = "00000000-0000-4000-8000-000000000001"
AT = "2026-10-22T18:00:00+02:00"
TX = "/api/imperium/vault"
FIN = "/api/vault"


def example(method: str, path: str, schema: str, body: dict) -> dict:
    validated = MODELS[schema].model_validate(body)
    return {"synthetic": True, "method": method, "path": path, "schema": schema,
            "body": validated.model_dump(mode="json", exclude_unset=True)}


def request_examples() -> list[dict]:
    rows = [
        ("POST", TX + "/transactions", "ImperiumVaultTransactionCreate",
         {"transaction_type": "expense", "amount_cents": 4520, "currency": "EUR",
          "wallet": "cash", "occurred_at": AT, "timezone": "Europe/Paris",
          "category": "carburant", "source": "manual", "note": "Station de démonstration"}),
        ("POST", TX + "/transactions", "ImperiumVaultTransactionCreate",
         {"transaction_type": "income", "amount_cents": 12500, "currency": "EUR",
          "wallet": "bank", "occurred_at": AT, "category": "vtc"}),
        ("POST", TX + "/transactions/{transaction_id}/reverse", "ImperiumVaultTransactionReverseRequest",
         {"reason": "Doublon saisi par erreur"}),
        ("POST", TX + "/transactions/{transaction_id}/correct", "ImperiumVaultTransactionCorrectRequest",
         {"reason": "Montant mal recopié", "amount_cents": 4250}),
        ("POST", TX + "/categories/suggest", "VaultCategorySuggestRequest",
         {"label": "TOTAL ENERGIES", "amount_cents": 4520, "transaction_type": "expense"}),
        ("POST", TX + "/categories/confirm", "VaultCategoryConfirmRequest",
         {"label": "TOTAL ENERGIES", "category": "carburant"}),
        ("POST", TX + "/receipt-extractions/{extraction_id}/validate", "VaultReceiptValidateRequest",
         {"amount_cents": 1240, "occurred_at": AT, "category": "courses", "wallet": "bank",
          "stock_lines": [{"name": "Pommes", "quantity": "1.000", "unit": "kg"}]}),
        ("POST", TX + "/receipt-extractions/{extraction_id}/validate", "VaultReceiptValidateRequest",
         {"amount_cents": 1240, "occurred_at": AT, "category": "courses", "wallet": "bank", "stock_lines": []}),
        ("POST", FIN + "/wallet/snapshots", "WalletSnapshotCreate",
         {"cash_cents": 12000, "bank_cents": -3000, "crypto_cents": 5000, "recorded_at": AT}),
        ("POST", FIN + "/upcoming-expenses", "UpcomingExpenseCreate",
         {"label_fr": "Loyer fictif", "amount": "600.00", "due_date": "2026-11-01",
          "recurrence": "monthly", "category": "loyer", "wallet": "bank", "mandatory": True}),
        ("PATCH", FIN + "/upcoming-expenses/{expense_id}", "UpcomingExpenseUpdate",
         {"amount": "620.00", "recurrence": None}),
        ("POST", FIN + "/upcoming-expenses/{expense_id}/mark-paid", "UpcomingExpensePay", {}),
        ("POST", FIN + "/pressure/corrections", "PressureCorrectionCreate",
         {"kind": "postponed", "upcoming_expense_id": ID, "postponed_until": "2026-11-08", "reason": "Report convenu"}),
        ("POST", FIN + "/pressure/corrections", "PressureCorrectionCreate",
         {"kind": "handled", "upcoming_expense_id": ID, "reason": "Déjà prise en charge"}),
        ("POST", FIN + "/pressure/corrections", "PressureCorrectionCreate",
         {"kind": "exceptional_week", "week_start": "2026-10-19", "reason": "Semaine atypique"}),
    ]
    return [example(*row) for row in rows]


def response_examples() -> list[dict]:
    transaction = {"id": ID, "transaction_type": "expense", "amount_cents": 4520,
                   "currency": "EUR", "wallet": "cash", "occurred_at": AT,
                   "local_date": "2026-10-22", "timezone": "Europe/Paris",
                   "category": "carburant", "source": "manual", "note": "Exemple fictif",
                   "external_ref": None, "created_at": AT, "is_reversal": False}
    rows = [
        ("GET", TX + "/transactions", "ImperiumVaultTransactionListResponse",
         {"items": [transaction], "count": 1, "limit": 50, "offset": 0}),
        ("GET", TX + "/transactions", "ImperiumVaultTransactionListResponse",
         {"items": [], "count": 0, "limit": 50, "offset": 0}),
        ("GET", TX + "/transactions/{transaction_id}", "ImperiumVaultTransactionDetailResponse",
         {"transaction": transaction}),
        ("GET", TX + "/summary", "ImperiumVaultSummaryResponse",
         {"currency": "EUR", "occurred_from": None, "occurred_to": None,
          "total_income_cents": 12500, "total_expense_cents": 4520, "net_cents": 7980,
          "transaction_count": 2, "income_count": 1, "expense_count": 1}),
        ("GET", TX + "/categories", "VaultCategoryListResponse",
         {"categories": [{"category": "carburant", "book": "business", "kind": "expense"},
                         {"category": "courses", "book": "personal", "kind": "expense"}]}),
        ("POST", TX + "/categories/suggest", "VaultCategorySuggestionRead",
         {"label_key": "total energies", "category": "carburant", "book": "business",
          "source": "table", "confidence": "high", "confirmations": 0}),
        ("POST", TX + "/categories/suggest", "VaultCategorySuggestionRead",
         {"label_key": "inconnu", "category": None, "book": None,
          "source": "none", "confidence": None, "confirmations": 0}),
        ("GET", FIN + "/pressure", "VaultPressureResponse",
         {"score": 55, "label": "attention", "daily_targets": {"minimum": "110.00", "comfortable": "132.00", "optimal": "154.00"}, "computed_at": AT}),
        ("GET", FIN + "/wallet", "WalletStateRead",
         {"snapshot": None, "predicted_cash_cents": None, "predicted_bank_cents": None,
          "predicted_crypto_cents": None, "predicted_total_cents": None,
          "transactions_since": 0, "other_wallets_cents": {}, "check_suggested": False,
          "message": "Aucun relevé pour le moment."}),
        ("GET", FIN + "/wallet", "WalletStateRead",
         {"snapshot": {"id": ID, "cash_cents": 12000, "bank_cents": -3000,
                       "crypto_cents": 5000, "total_cents": 14000, "recorded_at": AT,
                       "source": "manual", "note": None},
          "predicted_cash_cents": 12000, "predicted_bank_cents": -3000,
          "predicted_crypto_cents": 5000, "predicted_total_cents": 14000,
          "transactions_since": 0, "other_wallets_cents": {}, "check_suggested": False, "message": None}),
        ("GET", TX + "/receipt-extractions/{extraction_id}", "VaultReceiptExtractionRead",
         {"id": ID, "entry_app": "vault", "status": "ready", "original_filename": "ticket-demo.jpg",
          "mime_type": "image/jpeg", "size_bytes": 12000, "ocr_confidence": 0.92,
          "draft": {"merchant": "Magasin fictif", "purchase_date": "2026-10-22",
                    "total_cents": 1240, "wallet": "bank", "category": "courses",
                    "book": "personal", "line_items": [], "warnings": []},
          "error_message": None, "transaction_id": None, "created_at": AT, "validated_at": None}),
        ("GET", TX + "/receipt-extractions/{extraction_id}", "VaultReceiptExtractionRead",
         {"id": ID, "entry_app": "vault", "status": "failed", "original_filename": "ticket-demo.jpg",
          "mime_type": "image/jpeg", "size_bytes": 12000, "ocr_confidence": None,
          "draft": None, "error_message": "Ticket illisible.", "transaction_id": None,
          "created_at": AT, "validated_at": None}),
    ]
    return [example(*row) for row in rows]


def ui_scenarios() -> dict:
    names = ["Tableau de bord", "Ajouter un gain", "Ajouter une dépense", "Scanner un ticket",
             "Vérifier le ticket", "Comprendre la pression", "Transactions", "Détail et correction",
             "Catégories", "Mettre à jour les soldes", "Dépenses à venir", "Réglages"]
    return {"synthetic": True, "screens": [{"screen": f"VAU-{i:02}", "title": title}
            for i, title in enumerate(names, 1)], "shared_states": {
                "loading": "Chargement indépendant", "empty": "Absence réelle, sans faux zéro",
                "ready": "Données serveur", "error": "Erreur lisible, saisie conservée",
                "offline": "Cache horodaté", "conflict": "Relire avant nouvelle action",
                "disabled": "Capacité non raccordée", "stale": "Date métier conservée",
                "pending": "Intention locale non enregistrée", "syncing": "Envoi en cours"},
            "path_parameters": {key: ID for key in ("transaction_id", "extraction_id", "expense_id", "correction_id")},
            "notes": "Instantanés indépendants de démonstration ; jamais envoyés automatiquement."}


def build(output: Path) -> Path:
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    final_folder, archive = output / NAME, output / f"{NAME}.zip"
    if final_folder.exists() or archive.exists():
        raise FileExistsError("Cette livraison existe déjà ; choisir un nouveau dossier.")
    git_executable = shutil.which("git")
    if git_executable is None:
        raise RuntimeError("git est requis pour identifier la source de la livraison.")
    source_files = [ROOT / "docs_master" / name for name in SOURCE_NAMES]
    contract_sources = [ROOT / "backend/app/schemas/vault.py", ROOT / "backend/app/schemas/imperium.py",
                        ROOT / "backend/app/api/v1/router.py",
                        *sorted((ROOT / "backend/app/api/v1/routes").glob("*vault*.py"))]
    fingerprints = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in source_files + contract_sources}
    with tempfile.TemporaryDirectory(prefix=".vault-build-", dir=output) as temporary:
        folder = Path(temporary) / NAME
        copy_documents(ROOT / "deliveries/vault_frontend", folder)
        for source in source_files:
            if source.is_symlink() or not source.is_file():
                raise ValueError("Source documentaire non régulière.")
            destination = folder / "sources" / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.name == "59_DESIGN_SYSTEM_V1_DRAFT.md":
                content = source.read_text(encoding="utf-8")
                foundations = content.split("## 12. IMPERIUM SCREEN ARCHITECTURE MAPPING V1", 1)[0]
                vault_screens = content.split("## 13. VAULT SCREEN ARCHITECTURE MAPPING V1", 1)[1].split("## 14. VECTOR SCREEN ARCHITECTURE MAPPING V1", 1)[0]
                destination.with_name("59_DESIGN_FOUNDATIONS_EXTRACT.md").write_text(foundations, encoding="utf-8")
                destination.with_name("59_VAULT_SCREEN_EXTRACT.md").write_text(
                    "# Extrait doc 59 — écrans Vault\n\n> Routes historiques : appliquer le document 11 du kit.\n\n" + vault_screens,
                    encoding="utf-8")
            else:
                shutil.copyfile(source, destination)
        schema = export_contract()
        write_json(folder / "contracts/openapi.json", schema)
        write_contract_guides(folder / "contracts", schema)
        write_json(folder / "examples/requests.json", request_examples())
        write_json(folder / "examples/responses.json", response_examples())
        write_json(folder / "examples/ui_scenarios.json", ui_scenarios())
        for relative in ("scripts/build_vault_frontend_kit.py", "scripts/serve_vault_frontend_kit.py",
                         "backend/tests/test_vault_frontend_kit.py"):
            destination = folder / "tooling" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        # Refuse une archive incohérente si les sources changent pendant sa construction.
        for relative, digest in fingerprints.items():
            if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
                raise RuntimeError("Sources modifiées pendant l'export ; relancer dans un nouveau processus.")
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "reference_commit": subprocess.check_output(  # nosec B603
                # Exécutable résolu, arguments fixes du dépôt ; jamais de shell ni saisie utilisateur.
                [git_executable, "-C", str(ROOT), "rev-parse", "HEAD"], text=True
            ).strip(),
            "synthetic_examples_only": True, "source_fingerprints": fingerprints,
            "operation_count": sum(method in METHODS for ops in schema["paths"].values() for method in ops),
            "files": {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(folder.rglob("*")) if p.is_file()},
        }
        write_json(folder / "manifest.json", manifest)
        staged = Path(temporary) / archive.name
        with zipfile.ZipFile(staged, "w", zipfile.ZIP_DEFLATED) as zipped:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    zipped.write(path, f"{NAME}/{path.relative_to(folder)}")
        shutil.move(str(folder), final_folder)
        shutil.move(str(staged), archive)
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    print(build(parser.parse_args().output))
