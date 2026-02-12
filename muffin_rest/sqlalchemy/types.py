from typing import Any

from sqlalchemy import sql
from typing_extensions import TypeVar  # py310,py311,py312

TVCollection = TypeVar("TVCollection", bound=sql.Select, default=sql.Select)

TResource = dict[str, Any]
TVResource = TypeVar("TVResource", bound=TResource, default=TResource)
