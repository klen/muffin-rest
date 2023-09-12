"""REST Utils."""
from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Dict, Iterable, Mapping, Tuple, Type

if TYPE_CHECKING:
    from muffin import Request

    from muffin_rest.types import TVCollection


class Mutate(abc.ABC):
    """Mutate collections."""

    field: Any = None

    def __init__(self, name: str, *, field=None, **meta):
        """Initialize a name."""
        self.name = name
        self.field = field if field is not None else self.field or name
        self.meta = meta

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self.name}'>"

    @abc.abstractmethod
    async def apply(self, collection: TVCollection) -> TVCollection:
        """Apply the mutation."""
        raise NotImplementedError


class Mutator(abc.ABC):
    """Mutate collections."""

    MUTATE_CLASS: Type[Mutate]
    mutations: Mapping[str, Mutate]

    def __init__(self, handler, params: Iterable):
        """Initialize the mutations."""
        self.handler = handler
        self.mutations = {}
        for param in params:
            obj, meta = param if isinstance(param, tuple) else (param, {})
            mut = self.convert(obj, **meta)
            if mut:
                self.mutations[mut.name] = mut

    def __iter__(self):
        """Iterate through self filters."""
        return iter(self.mutations)

    def __str__(self) -> str:
        """Describe the filters."""
        return ",".join(self.mutations)

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self}'>"

    def __bool__(self):
        return bool(self.mutations)

    def convert(self, obj, **meta) -> Mutate:
        """Convert params to mutations."""
        if isinstance(obj, self.MUTATE_CLASS):
            return obj

        return self.MUTATE_CLASS(obj, **meta)

    @abc.abstractmethod
    async def apply(
        self, request: Request, collection: TVCollection
    ) -> Tuple[TVCollection, Dict[str, Any]]:
        """Mutate a collection."""
        raise NotImplementedError
