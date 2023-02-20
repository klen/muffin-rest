from typing import Any, Awaitable, Callable, TypeVar

from muffin import Request

TVCollection = TypeVar("TVCollection", bound=Any)
TVResource = TypeVar("TVResource", bound=Any)
TAuth = Callable[[Request], Awaitable]
TVAuth = TypeVar("TVAuth", bound=TAuth)
