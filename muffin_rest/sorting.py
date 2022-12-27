"""Implement sorting."""

from typing import Any, Dict, Generator, List, Sequence, Tuple

from muffin import Request
from muffin.handler import Handler

from .utils import TCOLLECTION, Mutate, Mutator

SORT_PARAM = "sort"


class Sort(Mutate):
    """Sort a collection."""

    async def apply(self, collection, desc: bool = False, **_) -> Any:
        """Sort the collection."""
        return sorted(collection, key=lambda obj: getattr(obj, self.name), reverse=desc)


class Sorting(Mutator):

    """Build sorters for handlers."""

    MUTATE_CLASS = Sort
    mutations: Dict[str, Sort]  # type: ignore

    def __init__(self, handler: Handler, params: Sequence):
        """Initialize the sorting."""
        self.default: List[Sort] = []
        super(Sorting, self).__init__(handler, params)

    async def apply(
        self, request: Request, collection: TCOLLECTION, **_
    ) -> TCOLLECTION:
        """Sort the given collection."""
        data = request.url.query.get(SORT_PARAM)
        if data:
            for name, desc in to_sort(data.split(",")):
                if name in self.mutations:
                    collection = await self.mutations[name].apply(collection, desc)

        elif self.default:
            return self.sort_default(collection)

        return collection

    def convert(self, obj, **meta) -> Sort:
        """Prepare sorters."""
        sort: Sort = super(Sorting, self).convert(obj, **meta)  # type: ignore
        if sort.meta.get("default"):
            self.default.append(sort)
        return sort

    def sort_default(self, collection: TCOLLECTION) -> TCOLLECTION:
        """Sort by default."""
        return sorted(collection)  # type: ignore

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
