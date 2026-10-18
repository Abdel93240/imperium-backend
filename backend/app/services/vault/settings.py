"""Réglages Vault (VAU-12, doc 59 §13.12) : synthèse en lecture seule.

Le pourcentage sadaqa est lu dans Path (source qui gagne, doc 41 §9.1) ; les autres lignes
mènent aux écrans qui portent les vraies saisies : catégories (VAU-09), soldes (VAU-10),
échéances (VAU-11). « Synchronisation » = dernier bénéfice hebdomadaire et dernière pression
calculés. Aucun réglage propre au Vault n'est défini : pas de modification ici.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.vault import PressureSnapshot, UpcomingExpense, WeeklyFinanceSummary
from app.schemas.vault import VaultSettingsRead, VaultSettingsRow
from app.services.path import sadaqa
from app.services.vault import categorization, wallet


def vault_settings(db: Session, *, current_user: User) -> VaultSettingsRead:
    path_settings = sadaqa.get_settings(db, current_user=current_user)
    categories = len(categorization.get_referential(db))
    snapshot = wallet.latest_snapshot(db, current_user)
    upcoming = db.scalar(
        select(func.count()).select_from(UpcomingExpense).where(
            UpcomingExpense.user_id == current_user.id, UpcomingExpense.active.is_(True)
        )
    ) or 0
    weekly = db.scalar(select(func.max(WeeklyFinanceSummary.computed_at)).where(WeeklyFinanceSummary.user_id == current_user.id))
    pressure = db.scalar(select(func.max(PressureSnapshot.computed_at)).where(PressureSnapshot.user_id == current_user.id))
    percent = (path_settings.percentage * 100).normalize()
    rows = [
        VaultSettingsRow(key="sadaqa", label="Pourcentage sadaqa (réglé dans Path)", value=f"{percent:f} %".replace(".", ","),
                         complete=True, target="PAT-11d"),
        VaultSettingsRow(key="categories", label="Catégories", value=f"{categories} catégories", complete=categories > 0,
                         target="VAU-09"),
        VaultSettingsRow(key="wallet", label="Soldes réels",
                         value=f"Relevé du {snapshot.recorded_at:%d/%m/%Y}" if snapshot else None,
                         complete=snapshot is not None, target="VAU-10"),
        VaultSettingsRow(key="upcoming", label="Dépenses à venir", value=f"{upcoming} active(s)", complete=upcoming > 0,
                         target="VAU-11"),
    ]
    return VaultSettingsRead(
        sadaqa_percentage=path_settings.percentage, sadaqa_safety_margin=path_settings.safety_margin, sadaqa_source="path",
        categories_count=categories, last_wallet_snapshot_at=snapshot.recorded_at if snapshot else None,
        active_upcoming_expenses=upcoming, last_weekly_summary_at=weekly, last_pressure_at=pressure, rows=rows,
        completion=sum(row.complete for row in rows),
    )
