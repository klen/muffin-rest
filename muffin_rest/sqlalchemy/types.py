from typing import Any, TypeVar

from sqlalchemy import sql

TVCollection = TypeVar("TVCollection", bound=sql.Select)

TResource = dict[str, Any]
TVResource = TypeVar("TVResource", bound=TResource)
