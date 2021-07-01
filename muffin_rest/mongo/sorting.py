"""Support sorting for Mongo ORM."""

import typing as t

from ..sorting import Sort, Sorting

from .utils import MongoChain


TCOLLECTION = t.TypeVar('TCOLLECTION', bound=MongoChain)


class MongoSort(Sort):
    """Sorter for Peewee."""

    def apply(self, collection, desc: bool = False, **options):
        """Sort the collection."""
        collection.sorting.append((self.field, -1 if desc else 1))
        return collection


class MongoSorting(Sorting):
    """Sort Peewee ORM Queries."""

    MUTATE_CLASS = MongoSort

    def sort_default(self, collection: TCOLLECTION) -> TCOLLECTION:  # type: ignore
        """Sort collection by default."""
        return collection.sort(
            [(sort.name, -1 if sort.meta['default'] == 'desc' else 1) for sort in self.default])
