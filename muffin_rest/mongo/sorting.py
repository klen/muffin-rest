"""Support sorting for Mongo ORM."""

from __future__ import annotations

from typing import Any

from muffin_rest.sorting import Sort, Sorting


class MongoSort(Sort):
    """Sorter for Peewee."""

    def __init__(self, name: str, *, field: str | None = None, **meta: Any) -> None:
        super().__init__(name, **meta)
        self.field = field if field is not None else (getattr(self, "field", None) or name)

    async def apply(self, collection: Any, *, desc: bool = False, **ctx: Any) -> Any:
        """Sort the collection."""
        collection.sorting.append((self.field, -1 if desc else 1))
        return collection


class MongoSorting(Sorting):
    """Sort Peewee ORM Queries."""

    MUTATE_CLASS = MongoSort

    def sort_default(self, collection: Any) -> Any:
        """Sort collection by default."""
        res = collection.sort(
            [(sort.name, -1 if sort.meta["default"] == "desc" else 1) for sort in self.default],
        )
        return res
