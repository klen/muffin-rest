import sys
from typing import Any

if sys.version_info < (3, 13):
    from typing_extensions import TypeVar  # py310,py311,py312
else:
    from typing import TypeVar

from .utils import MongoChain

TResource = dict[str, Any]
TVCollection = TypeVar("TVCollection", bound=MongoChain, default=MongoChain)
TVResource = TypeVar("TVResource", bound=TResource, default=TResource)
