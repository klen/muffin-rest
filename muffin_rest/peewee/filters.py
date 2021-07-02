"""Support filters for Peewee ORM."""

import typing as t
from peewee import Query, Field
import marshmallow as ma

from ..filters import Filter, Filters


class PWFilter(Filter):
    """Support Peewee."""

    operators = Filter.operators
    operators['$in'] = lambda f, v: f << v
    operators['$none'] = lambda f, v: f >> v
    operators['$like'] = lambda f, v: f % v
    operators['$ilike'] = lambda f, v: f ** v
    operators['$contains'] = lambda f, v: f.contains(v)
    operators['$starts'] = lambda f, v: f.startswith(v)
    operators['$ends'] = lambda f, v: f.endswith(v)
    operators['$between'] = lambda f, v: f.between(*v)
    operators['$regexp'] = lambda f, v: f.regexp(v)

    list_ops = Filter.list_ops + ['$between']

    def __init__(self, name: str, *, field: Field = None,
                 schema_field: ma.fields.Field = None, operator: str = None, **meta):
        """Support custom model fields."""
        self.name = name
        self.field = field
        self.schema_field = schema_field or self.schema_field_cls(
            attribute=field and field.name or name)
        if operator:
            self.default_operator = operator

    def apply(self, collection: Query, *ops: t.Tuple[t.Callable, t.Any], **kwargs) -> Query:
        """Apply the filters to Peewee QuerySet.."""
        if ops:
            return self.query(collection, self.field, *ops, **kwargs)
        return collection

    def query(self, query: Query, column: Field, *ops: t.Tuple, **kwargs) -> Query:
        """Filter a query."""
        if isinstance(column, Field):
            return query.where(*[op(column, val) for op, val in ops])

        return query


class PWFilters(Filters):
    """Bind Peewee filter class."""

    MUTATE_CLASS = PWFilter

    def convert(self, obj: t.Union[str, Field, PWFilter], **meta):
        """Convert params to filters."""
        from . import PWRESTHandler

        handler = t.cast(PWRESTHandler, self.handler)
        if isinstance(obj, PWFilter):
            if obj.field is None:
                obj.field = handler.meta.model._meta.fields.get(obj.name)
            return obj

        if isinstance(obj, Field):
            name = obj.name
            field = obj

        else:
            name = obj
            field = meta.pop('field', None) or name
            if isinstance(field, str):
                field = handler.meta.model._meta.fields.get(field)

        schema_field = meta.pop('schema_field', None)
        if schema_field is None and field:
            schema_field = handler.meta.Schema._declared_fields.get(field.name)
        return self.MUTATE_CLASS(name, field=field, schema_field=schema_field, **meta)
