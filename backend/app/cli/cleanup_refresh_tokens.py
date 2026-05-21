import sys
from datetime import UTC, datetime

from sqlalchemy import delete, exists, func, select, text
from sqlalchemy.orm import Session, aliased

from app.db.session import SessionLocal
from app.models.auth import RefreshToken


def main() -> int:
    try:
        with SessionLocal() as db:
            _assert_imperium_core(db)
            now = datetime.now(UTC)
            referencing_token = aliased(RefreshToken)
            deletable = ~exists(
                select(referencing_token.id).where(referencing_token.replaced_by_token_id == RefreshToken.id)
            )
            expired_count = db.scalar(
                select(func.count())
                .select_from(RefreshToken)
                .where(RefreshToken.expires_at <= now, deletable)
            )
            result = db.execute(delete(RefreshToken).where(RefreshToken.expires_at <= now, deletable))
            db.commit()
    except Exception as exc:
        print(f"Failed to clean expired refresh tokens: {exc}", file=sys.stderr)
        return 1

    print(f"Expired refresh tokens deleted: {result.rowcount or expired_count or 0}")
    return 0


def _assert_imperium_core(db: Session) -> None:
    current_database = db.execute(text("select current_database()")).scalar_one()
    if current_database != "imperium_core":
        raise RuntimeError(f"Refusing to run on database '{current_database}'. Expected 'imperium_core'.")


if __name__ == "__main__":
    raise SystemExit(main())
