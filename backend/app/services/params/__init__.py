"""Versioned append-only parameters access (table `parameters`, view
`v_parameters_current`).

Reading goes through the view (latest non-superseded version per code).
Writing NEVER updates a value in place: it inserts version+1 and points the
previous row's superseded_by to the new row (the only column the append-only
guard lets change).
"""

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.toolbox import Parameter


class ParameterNotFoundError(LookupError):
    pass


def get_parameter(db: Session, code: str, default: Any = ...) -> Any:
    row = db.execute(
        text("SELECT value FROM v_parameters_current WHERE code = :code"),
        {"code": code},
    ).first()
    if row is None:
        if default is ...:
            raise ParameterNotFoundError(f"Unknown parameter '{code}'.")
        return default
    return row[0]


def set_parameter(
    db: Session,
    *,
    code: str,
    value: Any,
    origin: str,
    rationale_fr: str,
    unit: str | None = None,
    sources: dict | None = None,
) -> Parameter:
    current = db.scalar(
        select(Parameter)
        .where(Parameter.code == code, Parameter.superseded_by.is_(None))
        .order_by(Parameter.version.desc())
        .limit(1)
    )
    new_row = Parameter(
        id=uuid4(),
        code=code,
        domain=current.domain if current is not None else code.split(".", 1)[0],
        value=json.loads(json.dumps(value)),
        unit=unit if unit is not None else (current.unit if current is not None else None),
        rationale_fr=rationale_fr,
        sources=sources,
        origin=origin,
        version=(current.version + 1) if current is not None else 1,
    )
    db.add(new_row)
    db.flush()
    if current is not None:
        current.superseded_by = new_row.id
    db.flush()
    return new_row
