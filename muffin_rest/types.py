from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Type,
    TypeVar,
)

if TYPE_CHECKING:
    from .handler import RESTBase

from muffin import Request

TVCollection = TypeVar("TVCollection", bound=Any)
TVResource = TypeVar("TVResource", bound=Any)
TAuth = Callable[[Request], Awaitable]
TVAuth = TypeVar("TVAuth", bound=TAuth)
TVHandler = TypeVar("TVHandler", bound=Type["RESTBase"])
TSchemaRes = Dict[str, Any]
