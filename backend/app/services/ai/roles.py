"""Role → model resolution against ai_role_models (doc 73 PART B, doc 30 §3).

The code never hard-codes a concrete model id (DV-6): it names a ROLE and this
module resolves the active row with the highest version. The seed values live in
migration 20260715_0039; doc 30 §3 stays the owner of the role list.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.toolbox import AIRoleModel

LOCAL_EXECUTOR_ROLE = "local_executor"

# Last-resort fallback when the table is unreachable/empty (mirrors the seed).
# Kept in sync with migration 20260715_0039; the DB row is the source of truth.
_FALLBACK_MODEL_IDS = {
    LOCAL_EXECUTOR_ROLE: "qwen3-32b",
}


class RoleResolutionError(RuntimeError):
    pass


def resolve_role(db: Session, role_code: str) -> AIRoleModel:
    row = db.scalar(
        select(AIRoleModel)
        .where(AIRoleModel.role_code == role_code, AIRoleModel.active.is_(True))
        .order_by(AIRoleModel.version.desc())
        .limit(1)
    )
    if row is None:
        raise RoleResolutionError(f"No active ai_role_models row for role '{role_code}'.")
    return row


def resolve_model_id(role_code: str, db: Session | None = None) -> str:
    """Resolve the concrete model id for a role, with a safe seed-mirroring fallback.

    A missing table/row must never crash a dry-run code path: the fallback keeps
    the identifier-not-call contract while the DB row remains authoritative.
    """
    if db is not None:
        try:
            return resolve_role(db, role_code).model_id
        except RoleResolutionError:
            pass
    else:
        try:
            from app.db.session import SessionLocal

            with SessionLocal() as session:
                return resolve_role(session, role_code).model_id
        except Exception:  # pragma: no cover - DB unavailable, fall back to seed mirror
            pass
    fallback = _FALLBACK_MODEL_IDS.get(role_code)
    if fallback is None:
        raise RoleResolutionError(f"Role '{role_code}' has no row and no fallback.")
    return fallback
