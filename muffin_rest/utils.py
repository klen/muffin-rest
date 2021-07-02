"""REST Utils."""

import typing as t

from muffin import Request


TCOLLECTION = t.TypeVar('TCOLLECTION')


class Mutate:
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

    def apply(self, collection: TCOLLECTION, **options) -> TCOLLECTION:
        """Apply the mutation."""
        raise NotImplementedError


class Mutator:
    """Mutate collections."""

    MUTATE_CLASS = Mutate

    def __init__(self, handler, params: t.Sequence):
        """Initialize the mutations."""
        from .handler import RESTHandler

        self.handler = t.cast(RESTHandler, handler)
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
        return ','.join(self.mutations)

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self}'>"

    def __bool__(self):
        return bool(self.mutations)

    def convert(self, obj, **meta):
        """Convert params to mutations."""
        if isinstance(obj, self.MUTATE_CLASS):
            return obj

        return self.MUTATE_CLASS(obj, **meta)

    def apply(self, request: Request, collection: TCOLLECTION, **options) -> TCOLLECTION:
        """Mutate a collection."""
        raise NotImplementedError
