"""Implement sorting."""
from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Mapping,
    Sequence,
    Tuple,
    Type,
    cast,
)

from .types import TVCollection
from .utils import Mutate, Mutator

if TYPE_CHECKING:
    from muffin import Request

    from .handler import RESTBase

SORT_PARAM = "sort"


class Sort(Mutate):
    """Sort a collection."""

    async def apply(self, collection, *, desc: bool = False) -> Any:
        """Sort the collection."""
        return sorted(collection, key=lambda obj: getattr(obj, self.name), reverse=desc)


class Sorting(Mutator):
    """Build sorters for handlers."""

    MUTATE_CLASS = Sort
    mutations: Mapping[str, Sort]

    def __init__(self, handler: Type[RESTBase], params: Iterable):
        """Initialize the sorting."""
        self.default: List[Sort] = []
        super(Sorting, self).__init__(handler, params)

    async def apply(
        self, request: Request, collection: TVCollection
    ) -> Tuple[TVCollection, Dict[str, Any]]:
        """Sort the given collection."""
        data = request.url.query.get(SORT_PARAM)
        sorting = {}
        if data:
            collection = self.prepare(collection)
            sorting = dict(to_sort(data.split(",")))
            for name in self.mutations:
                sort = self.mutations[name]
                if name in sorting:
                    desc = sorting[name]
                    collection = await sort.apply(collection, desc=desc)
                    sorting[sort.name] = desc

        elif self.default:
            return self.sort_default(collection), sorting

        return collection, sorting

    def prepare(self, collection: TVCollection) -> TVCollection:
        """Prepare the collection."""
        return collection

    def convert(self, obj, **meta) -> Sort:
        """Prepare sorters."""
        sort = cast(Sort, super(Sorting, self).convert(obj, **meta))
        if sort.meta.get("default"):
            self.default.append(sort)
        return sort

    def sort_default(self, collection: TVCollection) -> TVCollection:
        """Sort by default."""
        return cast(TVCollection, sorted(collection))

    @property
    def openapi(self):
        """Prepare OpenAPI params."""
        sorting = list(self.mutations)
        return {
            "name": SORT_PARAM,
            "in": "query",
            "style": "form",
            "explode": False,
            "schema": {"type": "array", "items": {"type": "string", "enum": sorting}},
            "description": ",".join(sorting),
        }


def to_sort(
    sort_params: Sequence[str],
) -> Generator[Tuple[str, bool], None, None]:
    """Generate sort params."""
    for name in sort_params:
        n, desc = name.strip("-"), name.startswith("-")
        if n:
            yield n, desc
