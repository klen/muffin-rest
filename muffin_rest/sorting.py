"""Implement sorting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generator, Iterable, Sequence

from .utils import Mutate, Mutator

if TYPE_CHECKING:
    from muffin import Request

    from .handler import RESTBase

SORT_PARAM = "sort"


class Sort(Mutate):
    """Sort a collection."""

    async def apply(self, collection: Any, *, desc: bool = False, **ctx: Any) -> Any:
        """Sort the collection (subclasses narrow the collection type)."""
        return sorted(collection, key=lambda obj: getattr(obj, self.name), reverse=desc)


class Sorting(Mutator[Sort]):
    """Build sorters for handlers."""

    MUTATE_CLASS = Sort

    def __init__(self, handler: type[RESTBase], params: Iterable[Any]) -> None:
        """Initialize the sorting."""
        self.default: list[Sort] = []
        super(Sorting, self).__init__(handler, params)

    async def apply(
        self, request: Request, collection: Any, **ctx: Any
    ) -> tuple[Any, dict[str, Any]]:
        """Sort the given collection."""
        data = request.url.query.get(SORT_PARAM)
        sorting = {}
        if data:
            collection = self.prepare(collection)
            for name, desc in to_sort(data.split(",")):
                sort = self.mutations.get(name)
                if sort:
                    collection = await sort.apply(collection, desc=desc, **ctx)
                    sorting[sort.name] = desc

        elif self.default:
            return self.sort_default(collection), sorting

        return collection, sorting

    def prepare(self, collection: Any) -> Any:
        """Prepare the collection."""
        return collection

    def convert(self, obj: Any, **meta: Any) -> Sort | None:
        """Prepare sorters."""
        sort = super(Sorting, self).convert(obj, **meta)

        if sort and sort.meta.get("default"):
            self.default.append(sort)

        return sort

    def sort_default(self, collection: Any) -> Any:
        """Sort by default."""
        return sorted(collection)

    @property
    def openapi(self) -> dict[str, Any]:
        """Prepare OpenAPI params."""
        sorting = [s for name in self.mutations for s in (name, f"-{name}")]
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
) -> Generator[tuple[str, bool], None, None]:
    """Generate sort params."""
    for name in sort_params:
        n, desc = name.strip("-"), name.startswith("-")
        if n:
            yield n, desc
