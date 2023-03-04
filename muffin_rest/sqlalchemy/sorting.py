"""Support sorting for SQLAlchemy ORM."""
from __future__ import annotations

from typing import TYPE_CHECKING, Union, cast

from sqlalchemy import Column

from muffin_rest.sorting import Sort, Sorting

if TYPE_CHECKING:
    from .types import TVCollection


class SASort(Sort):
    """Sorter for Peewee."""

    async def apply(
        self, collection: TVCollection, *, desc: bool = False, **_,
    ) -> TVCollection:
        """Sort the collection."""
        field = self.field
        if desc and isinstance(field, Column):
            field = field.desc()

        return collection.order_by(field)


class SASorting(Sorting):
    """Sort Peewee ORM Queries."""

    MUTATE_CLASS = SASort

    def convert(self, obj: Union[str, Column, SASort], **meta):
        """Prepare sorters."""
        from . import SARESTHandler

        if isinstance(obj, SASort):
            return obj

        handler = cast(SARESTHandler, self.handler)

        if isinstance(obj, Column):
            name, field = obj.name, obj

        else:
            name = obj
            field = meta.get("field", handler.meta.table.c.get(name))

        if field is not None:
            sort = self.MUTATE_CLASS(name, field=field, **meta)
            if sort.meta.get("default"):
                self.default.append(sort)

            return sort

    def sort_default(self, collection: TVCollection) -> TVCollection:
        """Sort collection by default."""
        return collection.order_by(
            *[
                sort.field.desc() if sort.meta["default"] == "desc" else sort.field
                for sort in self.default
            ],
        )
