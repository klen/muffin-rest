from typing import TYPE_CHECKING, Any, Awaitable, Callable

from typing_extensions import TypeVar  # py310,py311,py312

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
