"""REST Utils."""

import abc
from typing import Sequence, Type, TypeVar, cast

from muffin import Request

TCOLLECTION = TypeVar("TCOLLECTION")


class Mutate(abc.ABC):
    """Mutate collections."""

    def __init__(self, name: str, *, field=None, **meta):
        """Initialize a name."""
        self.name = name
        self.field = name if field is None else field
        self.meta = meta

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self.name}'>"

    @abc.abstractmethod
    async def apply(self, collection: TCOLLECTION, **options) -> TCOLLECTION:
        """Apply the mutation."""
        raise NotImplementedError


class Mutator(abc.ABC):
    """Mutate collections."""

    MUTATE_CLASS: Type[Mutate]

    def __init__(self, handler, params: Sequence):
        """Initialize the mutations."""
        from .handler import RESTHandler

        self.handler = cast(RESTHandler, handler)
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
        self, request: Request, collection: TCOLLECTION, **options
    ) -> TCOLLECTION:
        """Mutate a collection."""
        raise NotImplementedError
