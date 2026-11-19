"""REST Utils."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Generic, Iterable, Iterator, Mapping, TypeVar

if TYPE_CHECKING:
    from muffin import Request

    from .handler import RESTBase


class Mutate(abc.ABC):
    """Mutate collections."""

    field: Any

    def __init__(self, name: str, **meta: Any) -> None:
        """Initialize a name."""
        self.name = name
        self.meta = meta

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} '{self.name}'>"

    @abc.abstractmethod
    async def apply(self, collection: Any, **ctx: Any) -> Any:
        """Apply the mutation to the collection (subclasses narrow the collection type)."""
        ...


M = TypeVar("M", bound=Mutate)


class Mutator(abc.ABC, Generic[M]):
    """Mutate collections."""

    MUTATE_CLASS: type[M]
    mutations: Mapping[str, M]

    def __init__(self, handler: type[RESTBase], params: Iterable[Any]) -> None:
        """Initialize the mutations."""
        self.handler = handler
        self.mutations = {}
        for param in params:
            obj, meta = param if isinstance(param, tuple) else (param, {})
            mut = self.convert(obj, **meta)
            if mut:
                self.mutations[mut.name] = mut

    def __iter__(self) -> Iterator[str]:
        """Iterate through self filters."""
        return iter(self.mutations)

    def __str__(self) -> str:
        """Describe the filters."""
        return ",".join(self.mutations)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} '{self}'>"

    def __bool__(self) -> bool:
        return bool(self.mutations)

    def convert(self, obj: Any, **meta: Any) -> M | None:
        """Convert params to mutations."""
        factory = self.MUTATE_CLASS
        if not isinstance(obj, factory):
            obj = factory(obj, **meta)

        return obj

    @abc.abstractmethod
    async def apply(
        self, request: Request, collection: Any, **ctx: Any
    ) -> tuple[Any, dict[str, Any]]:
        """Mutate a collection (subclasses narrow the collection type)."""
        ...
