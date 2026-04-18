import sys
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeVar

if sys.version_info < (3, 13):
    from typing_extensions import TypeVar  # py310,py311,py312
else:
    from typing import TypeVar

if TYPE_CHECKING:
    from .handler import RESTBase

from muffin import Request

TVResource = TypeVar("TVResource", bound=Any, default=Any)
TVCollection = TypeVar("TVCollection", bound=Any, default=Any)

TAuth = Callable[[Request], Awaitable]
TVAuth = TypeVar("TVAuth", bound=TAuth)
TVHandler = TypeVar("TVHandler", bound=type["RESTBase"])
TSchemaRes = dict[str, Any]

TFilterValue = tuple[Callable, Any]
TFilterOps = tuple[TFilterValue, ...]
