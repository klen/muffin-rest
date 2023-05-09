from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Type,
    TypeVar,
    Union,
)

if TYPE_CHECKING:
    from .handler import RESTBase

from muffin import Request

TVCollection = TypeVar("TVCollection", bound=Any)
TVResource = TypeVar("TVResource", bound=Any)
TVData = Union[TVResource, List[TVResource]]
TAuth = Callable[[Request], Awaitable]
TVAuth = TypeVar("TVAuth", bound=TAuth)
TVHandler = TypeVar("TVHandler", bound=Type["RESTBase"])
TSchemaRes = Dict[str, Any]
