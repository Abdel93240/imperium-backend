from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.types import UserDefinedType


class Vector1024(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int | str = 1024) -> None:
        self.dimensions = int(dimensions)

    def get_col_spec(self, **_kw) -> str:
        return f"vector({self.dimensions})"


def register_postgresql_vector_type() -> None:
    PGDialect.ischema_names["vector"] = Vector1024
