from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    TypeVar,
    Union,
)

if TYPE_CHECKING:
    from .handler import RESTBase

from muffin import Request

TVCollection = TypeVar("TVCollection", bound=Any)
TVResource = TypeVar("TVResource", bound=Any)
TVData = Union[TVResource, list[TVResource]]
TAuth = Callable[[Request], Awaitable]
TVAuth = TypeVar("TVAuth", bound=TAuth)
TVHandler = TypeVar("TVHandler", bound=type["RESTBase"])
TSchemaRes = dict[str, Any]

TFilterValue = tuple[Callable, Any]
TFilterOps = tuple[TFilterValue, ...]
