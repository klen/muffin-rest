"""Support sorting for Peewee ORM."""

from __future__ import annotations

from typing import TYPE_CHECKING, Union, cast

from peewee import Field

from muffin_rest.sorting import Sort, Sorting

if TYPE_CHECKING:
    from .types import TVCollection


class PWSort(Sort):
    """Sorter for Peewee."""

    async def apply(
        self, collection: TVCollection, *, desc: bool = False, **_,
    ) -> TVCollection:
        """Sort the collection."""
        return collection.order_by_extend(self.field if not desc else self.field.desc())


class PWSorting(Sorting):
    """Sort Peewee ORM Queries."""

    MUTATE_CLASS = PWSort

    def convert(self, obj: Union[str, Field, PWSort], **meta):
        """Prepare sorters."""
        from . import PWRESTHandler

        if isinstance(obj, PWSort):
            return obj

        handler = cast(PWRESTHandler, self.handler)

        if isinstance(obj, Field):
            name, field = obj.name, obj

        else:
            name = obj
            field = meta.get("field", handler.meta.model._meta.fields.get(name))

        if field:
            sort = self.MUTATE_CLASS(name, field=field, **meta)
            if sort.meta.get("default"):
                self.default.append(sort)

            return sort

    def sort_default(self, collection: TVCollection) -> TVCollection:
        """Sort collection by default."""
        sorting = [
            sort.field.desc() if sort.meta["default"] == "desc" else sort.field
            for sort in self.default
        ]
        return collection.order_by(*sorting)
