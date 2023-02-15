from typing import Any, Dict, TypeVar

from .utils import MongoChain

TVCollection = TypeVar("TVCollection", bound=MongoChain)
TResource = Dict[str, Any]
TVResource = TypeVar("TVResource", bound=TResource)
