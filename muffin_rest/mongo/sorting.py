"""Support sorting for Mongo ORM."""

from ..sorting import Sort, Sorting
from .types import TVCollection


class MongoSort(Sort):
    """Sorter for Peewee."""

    async def apply(self, collection, desc: bool = False, **_):
        """Sort the collection."""
        collection.sorting.append((self.field, -1 if desc else 1))
        return collection


class MongoSorting(Sorting):
    """Sort Peewee ORM Queries."""

    MUTATE_CLASS = MongoSort

    def sort_default(self, collection: TVCollection) -> TVCollection:
        """Sort collection by default."""
        res = collection.sort(
            [
                (sort.name, -1 if sort.meta["default"] == "desc" else 1)
                for sort in self.default
            ]
        )
        return res
