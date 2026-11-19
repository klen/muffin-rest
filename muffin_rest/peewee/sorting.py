"""Support sorting for Peewee ORM."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from peewee import Field

from muffin_rest.sorting import Sort, Sorting

from .utils import get_model_field_by_name

if TYPE_CHECKING:
    from .types import TVCollection


class PWSort(Sort):
    """Sorter for Peewee."""

    def __init__(self, name: str, *, field: Field | str | None = None, **meta: Any) -> None:
        """Initialize the sorter."""
        super().__init__(name, **meta)
        self.field = field if field is not None else (getattr(self, "field", None) or name)

    async def apply(self, collection: Any, *, desc: bool = False, **ctx: Any) -> Any:
        """Sort the collection."""
        params = {"nulls": "LAST"} if isinstance(self.field, Field) and self.field.null else {}
        return collection.order_by_extend(
            self.field.asc(**params) if not desc else self.field.desc(**params)
        )


class PWSorting(Sorting):
    """Sort Peewee ORM Queries."""

    MUTATE_CLASS = PWSort

    def prepare(self, collection: Any) -> Any:
        """Prepare collection for sorting."""
        return collection.order_by()

    def convert(self, obj: Any, **meta: Any) -> Sort | None:
        """Prepare sorters."""

        if isinstance(obj, PWSort):
            return obj

        handler = self.handler

        if isinstance(obj, Field):
            name, field = obj.name, obj

        else:
            name = obj
            field = meta.pop("field", None) or name
            if isinstance(field, str):
                field = get_model_field_by_name(handler, field, stacklevel=6)

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
