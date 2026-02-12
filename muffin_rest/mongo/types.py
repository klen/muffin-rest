from typing import Any

from typing_extensions import TypeVar  # py310,py311,py312

from .utils import MongoChain

TResource = dict[str, Any]
TVCollection = TypeVar("TVCollection", bound=MongoChain, default=MongoChain)
TVResource = TypeVar("TVResource", bound=TResource, default=TResource)
