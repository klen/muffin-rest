"""Support sorting for Peewee ORM."""

from __future__ import annotations

from typing import TYPE_CHECKING, Type, Union, cast

from peewee import Field

from muffin_rest.sorting import SORT_PARAM, Sort, Sorting, to_sort

if TYPE_CHECKING:
    from muffin import Request

    from .types import TVCollection


class PWSort(Sort):
    """Sorter for Peewee."""

    async def apply(
        self, collection: TVCollection, *, desc: bool = False, **_
    ) -> TVCollection:
        """Sort the collection."""
        return collection.order_by_extend(self.field if not desc else self.field.desc())


class PWSorting(Sorting):
    """Sort Peewee ORM Queries."""

    MUTATE_CLASS: Type[PWSort] = PWSort

    async def apply(
        self, request: Request, collection: TVCollection, **_
    ) -> TVCollection:
        """Sort the given collection. Reset sorting."""
        data = request.url.query.get(SORT_PARAM)
        if data:
            collection = collection.order_by()
            for name, desc in to_sort(data.split(",")):
                sort = self.mutations.get(name)
                if sort:
                    collection = await sort.apply(collection, desc=desc)

        elif self.default:
            return self.sort_default(collection)

        return collection

    def convert(self, obj: Union[str, Field, PWSort], **meta):
        """Prepare sorters."""
        from . import PWRESTHandler

        if isinstance(obj, PWSort):
            return obj

        handler = cast(PWRESTHandler, self.handler)
        model_meta = handler.meta.model._meta  # type: ignore[]

        if isinstance(obj, Field):
            name, field = obj.name, obj

        else:
            name = obj
            field = meta.pop("field", model_meta.fields.get(name))

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
