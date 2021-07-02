"""Support sorting for SQLAlchemy ORM."""

import typing as t

from sqlalchemy import Column, sql

from ..sorting import Sort, Sorting


TCOLLECTION = t.TypeVar('TCOLLECTION', bound=sql.Select)


class SASort(Sort):
    """Sorter for Peewee."""

    def apply(self, collection: TCOLLECTION, desc: bool = False, **options) -> TCOLLECTION:
        """Sort the collection."""
        collection.append_order_by(self.field if not desc else self.field.desc())
        return collection


class SASorting(Sorting):
    """Sort Peewee ORM Queries."""

    MUTATE_CLASS = SASort

    def convert(self, obj: t.Union[str, Column, SASort], **meta):
        """Prepare sorters."""
        from . import SARESTHandler

        if isinstance(obj, SASort):
            return obj

        handler = t.cast(SARESTHandler, self.handler)

        if isinstance(obj, Column):
            name, field = obj.name, obj

        else:
            name = obj
            field = meta.get('field', handler.meta.table.c.get(name))

        if field is not None:
            sort = self.MUTATE_CLASS(name, field=field, **meta)
            if sort.meta.get('default'):
                self.default.append(sort)

            return sort

    def sort_default(self, collection: sql.Select) -> sql.Select:
        """Sort collection by default."""
        return collection.order_by(*[
            sort.field.desc() if sort.meta['default'] == 'desc' else sort.field
            for sort in self.default
        ])
