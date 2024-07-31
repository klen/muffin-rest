from typing import Any, TypeVar

from .utils import MongoChain

TResource = dict[str, Any]
TVCollection = TypeVar("TVCollection", bound=MongoChain)
TVResource = TypeVar("TVResource", bound=TResource)
