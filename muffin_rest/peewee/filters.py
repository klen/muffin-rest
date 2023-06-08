"""Support filters for Peewee ORM."""
from __future__ import annotations

import operator
from typing import Any, Callable, Optional, Tuple, Type, Union, cast
from warnings import warn

from peewee import Field, ModelSelect

from muffin_rest.filters import Filter, Filters


class PWFilter(Filter):
    """Support Peewee."""

    operators = Filter.operators
    operators["$in"] = operator.lshift
    operators["$none"] = operator.rshift
    operators["$like"] = operator.mod
    operators["$ilike"] = operator.pow
    operators["$contains"] = lambda f, v: f.contains(v)
    operators["$starts"] = lambda f, v: f.startswith(v)
    operators["$ends"] = lambda f, v: f.endswith(v)
    operators["$between"] = lambda f, v: f.between(*v)
    operators["$regexp"] = lambda f, v: f.regexp(v)

    list_ops = [*Filter.list_ops, "$between"]

    async def filter(
        self, collection: ModelSelect, *ops: Tuple[Callable, Any], **kwargs
    ) -> ModelSelect:
        """Apply the filters to Peewee QuerySet.."""
        if self.field and ops:
            return self.query(collection, self.field, *ops, **kwargs)
        return collection

    def query(self, qs: ModelSelect, column: Field, *ops: Tuple, **_) -> ModelSelect:
        """Filter a query."""
        if isinstance(column, Field):
            return cast(ModelSelect, qs.where(*[op(column, val) for op, val in ops]))

        return qs


class PWFilters(Filters):
    """Bind Peewee filter class."""

    MUTATE_CLASS: Type[PWFilter] = PWFilter

    def convert(self, obj: Union[str, Field, PWFilter], **meta):
        """Convert params to filters."""
        from . import PWRESTHandler

        handler = cast(PWRESTHandler, self.handler)
        if isinstance(obj, PWFilter):
            if obj.field is None:
                obj.field = get_model_field_by_name(handler, obj.name)
            return obj

        if isinstance(obj, Field):
            name = obj.name
            field = obj

        else:
            name = obj
            field = meta.pop("field", None) or name
            if isinstance(field, str):
                field = get_model_field_by_name(handler, field)

        schema_field = meta.pop("schema_field", None)
        if schema_field is None and field:
            schema_field = handler.meta.Schema._declared_fields.get(field.name)
        return self.MUTATE_CLASS(name, field=field, schema_field=schema_field, **meta)


def get_model_field_by_name(handler, name) -> Optional[Field]:
    """Get model field by name."""
    fields = handler.meta.model._meta.fields
    candidate = fields.get(name)
    if candidate:
        return candidate

    for field in fields.values():
        if field.column_name == name:
            return field

    warn(
        f"{handler.__qualname__} {handler.meta.model} has no field {name}",
        category=RuntimeWarning,
        stacklevel=5,
    )
    return None
