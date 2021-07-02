"""Support filters for SQLAlchemy ORM."""

import typing as t
from sqlalchemy import Column, sql
import marshmallow as ma

from ..filters import Filter, Filters


TCOLLECTION = t.TypeVar('TCOLLECTION', bound=sql.Select)


class SAFilter(Filter):
    """Custom filter for sqlalchemy."""

    operators = Filter.operators
    operators['$between'] = lambda c, v: c.between(*v)
    operators['$ends'] = lambda c, v: c.endswith(v)
    operators['$ilike'] = lambda c, v: c.ilike(v)
    operators['$in'] = lambda c, v: c.in_(v)
    operators['$like'] = lambda c, v: c.like(v)
    operators['$match'] = lambda c, v: c.match(v)
    operators['$nin'] = lambda c, v: ~c.in_(v)
    operators['$notilike'] = lambda c, v: c.notilike(v)
    operators['$notlike'] = lambda c, v: c.notlike(v)
    operators['$starts'] = lambda c, v: c.startswith(v)

    list_ops = Filter.list_ops + ['$between']

    def __init__(self, name: str, *, field: Column = None,
                 schema_field: ma.fields.Field = None, operator: str = None, **meta):
        """Support custom model fields."""
        self.name = name
        self.field = field
        self.schema_field = schema_field or self.schema_field_cls(
            attribute=field is not None and (field.key or field.name) or name)

        if operator:
            self.default_operator = operator

    def apply(self, collection: sql.Select,
              *ops: t.Tuple[t.Callable, t.Any], **kwargs) -> sql.Select:
        """Apply the filters to SQLAlchemy Select."""
        column = self.field
        if ops and column is not None:
            return self.query(collection, column, *ops, **kwargs)

        return collection

    def query(self, select: sql.Select, column: Column, *ops, **kwargs) -> sql.Select:
        """Filter a select."""
        return select.where(*[op(column, val) for op, val in ops])


class SAFilters(Filters):
    """Bind SAfilter class."""

    MUTATE_CLASS = SAFilter

    def convert(self, obj: t.Union[str, Column, SAFilter], **meta):
        """Convert params to filters."""
        from . import SARESTHandler

        handler = t.cast(SARESTHandler, self.handler)

        if isinstance(obj, SAFilter):
            if obj.field is None:
                obj.field = handler.meta.table.c.get(obj.name)
            return obj

        if isinstance(obj, Column):
            name = obj.name
            field = obj

        else:
            name = obj
            field = meta.pop('field', None) or name
            if isinstance(field, str):
                field = handler.meta.table.c.get(field)

        schema_field = meta.pop('schema_field', None)
        if schema_field is None and field is not None:
            schema_field = handler.meta.Schema._declared_fields.get(field.name)

        return self.MUTATE_CLASS(name, field=field, schema_field=schema_field, **meta)
