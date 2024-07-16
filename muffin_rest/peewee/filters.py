"""Support filters for Peewee ORM."""
from __future__ import annotations

import operator
from functools import reduce
from typing import Any, Callable, Tuple, Type, Union, cast

from peewee import ColumnBase, Field, ModelSelect

from muffin_rest.filters import Filter, Filters

from .utils import get_model_field_by_name


class PWFilter(Filter):
    """Support Peewee."""

    operators = dict(Filter.operators)
    operators["$in"] = operator.lshift
    operators["$none"] = operator.rshift
    operators["$like"] = operator.mod
    operators["$ilike"] = operator.pow
    operators["$contains"] = lambda f, v: f.contains(v)
    operators["$starts"] = lambda f, v: f.startswith(v)
    operators["$ends"] = lambda f, v: f.endswith(v)
    operators["$between"] = lambda f, v: f.between(*v)
    operators["$regexp"] = lambda f, v: f.regexp(v)
    operators["$null"] = lambda f, v: f.is_null(v)
    operators["$or"] = lambda col, value: reduce(operator.or_, [op(col, val) for op, val in value])
    operators["$and"] = lambda col, value: reduce(
        operator.and_, [op(col, val) for op, val in value]
    )

    list_ops = (*Filter.list_ops, "$between")

    async def filter(
        self, collection: ModelSelect, *ops: Tuple[Callable, Any], **kwargs
    ) -> ModelSelect:
        """Apply the filters to Peewee QuerySet.."""
        column = self.field
        if isinstance(column, ColumnBase):
            collection = cast(ModelSelect, collection.where(*[op(column, val) for op, val in ops]))
        return collection


class PWFilters(Filters):
    """Bind Peewee filter class."""

    MUTATE_CLASS: Type[PWFilter] = PWFilter

    def convert(self, obj: Union[str, Field, PWFilter], **meta):
        """Convert params to filters."""
        from . import PWRESTHandler

        handler = cast(PWRESTHandler, self.handler)
        if isinstance(obj, PWFilter):
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
            schema_field = handler.meta.Schema._declared_fields.get(name)
        return self.MUTATE_CLASS(name, field=field, schema_field=schema_field, **meta)
