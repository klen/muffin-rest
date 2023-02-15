from typing import Any, Dict, TypeVar

from sqlalchemy import sql

TVCollection = TypeVar("TVCollection", bound=sql.Select)

TResource = Dict[str, Any]
TVResource = TypeVar("TVResource", bound=TResource)
