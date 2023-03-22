"""Support filters for Peewee ORM."""
from __future__ import annotations

import operator
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple, Union, cast

from peewee import Field, ModelSelect

from muffin_rest.filters import Filter, Filters

if TYPE_CHECKING:
    import marshmallow as ma


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

    def __init__(
        self,
        name: str,
        *,
        field: Optional[Field] = None,
        schema_field: Optional[ma.fields.Field] = None,
        operator: Optional[str] = None,
        **_,
    ):
        """Support custom model fields."""
        self.name = name
        self.field = field
        self.schema_field = schema_field or self.schema_field_cls(
            attribute=field and field.name or name,
        )
        if operator:
            self.default_operator = operator

    async def filter(
        self,
        collection: ModelSelect,
        *ops: Tuple[Callable, Any],
        **kwargs,
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

    MUTATE_CLASS = PWFilter

    def convert(self, obj: Union[str, Field, PWFilter], **meta):
        """Convert params to filters."""
        from . import PWRESTHandler

        handler = cast(PWRESTHandler, self.handler)
        model_meta = handler.meta.model._meta  # type: ignore[]
        if isinstance(obj, PWFilter):
            if obj.field is None:
                obj.field = model_meta.fields.get(obj.name)
            return obj

        if isinstance(obj, Field):
            name = obj.name
            field = obj

        else:
            name = obj
            field = meta.pop("field", None) or name
            if isinstance(field, str):
                field = model_meta.fields.get(field)

        schema_field = meta.pop("schema_field", None)
        if schema_field is None and field:
            schema_field = handler.meta.Schema._declared_fields.get(field.name)
        return self.MUTATE_CLASS(name, field=field, schema_field=schema_field, **meta)
