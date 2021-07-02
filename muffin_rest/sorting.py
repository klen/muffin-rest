"""Implement sorting."""

import typing as t

from muffin import Request
from muffin.handler import Handler

from . import SORT_PARAM
from .utils import Mutate, Mutator, TCOLLECTION


class Sort(Mutate):
    """Sort a collection."""

    def apply(self, collection, desc: bool = False, **options):
        """Sort the collection."""
        return sorted(collection, key=lambda obj: getattr(obj, self.name), reverse=desc)


class Sorting(Mutator):

    """Build sorters for handlers."""

    MUTATE_CLASS = Sort

    def __init__(self, handler: Handler, params: t.Sequence):
        """Initialize the sorting."""
        self.default: t.List = []
        super(Sorting, self).__init__(handler, params)

    def convert(self, obj, **meta):
        """Prepare sorters."""
        sort = super(Sorting, self).convert(obj, **meta)
        if sort.meta.get('default'):
            self.default.append(sort)
        return sort

    def apply(self, request: Request, collection: TCOLLECTION, **options) -> TCOLLECTION:
        """Sort the given collection."""
        data = request.url.query.get(SORT_PARAM)
        if data:
            for name, desc in to_sort(data.split(',')):
                if name in self.mutations:
                    collection = self.mutations[name].apply(collection, desc)

        elif self.default:
            return self.sort_default(collection)

        return collection

    def sort_default(self, collection: TCOLLECTION) -> TCOLLECTION:
        """Sort by default."""
        return sorted(collection)  # type: ignore

    @property
    def openapi(self):
        """Prepare OpenAPI params."""
        sorting = list(self.mutations)
        return {
            'name': SORT_PARAM, 'in': 'query', 'style': 'form', 'explode': False,
            'schema': {'type': 'array', 'items': {'type': 'string', 'enum': sorting}},
            'description': ",".join(sorting),
        }


def to_sort(sort_params: t.Sequence[str]) -> t.Generator[t.Tuple[str, bool], None, None]:
    """Generate sort params."""
    for name in sort_params:
        n, desc = name.strip('-'), name.startswith('-')
        if n:
            yield n, desc
