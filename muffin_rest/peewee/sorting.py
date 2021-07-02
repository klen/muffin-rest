"""Support sorting for Peewee ORM."""

import typing as t

from peewee import Field, Query

from ..sorting import Sort, Sorting


TCOLLECTION = t.TypeVar('TCOLLECTION', bound=Query)


class PWSort(Sort):
    """Sorter for Peewee."""

    def apply(self, collection: TCOLLECTION, desc: bool = False, **options) -> TCOLLECTION:
        """Sort the collection."""
        return collection.order_by_extend(self.field if not desc else self.field.desc())


class PWSorting(Sorting):
    """Sort Peewee ORM Queries."""

    MUTATE_CLASS = PWSort

    def convert(self, obj: t.Union[str, Field, PWSort], **meta):
        """Prepare sorters."""
        from . import PWRESTHandler

        if isinstance(obj, PWSort):
            return obj

        handler = t.cast(PWRESTHandler, self.handler)

        if isinstance(obj, Field):
            name, field = obj.name, obj

        else:
            name = obj
            field = meta.get('field', handler.meta.model._meta.fields.get(name))

        if field:
            sort = self.MUTATE_CLASS(name, field=field, **meta)
            if sort.meta.get('default'):
                self.default.append(sort)

            return sort

    def sort_default(self, collection: TCOLLECTION) -> TCOLLECTION:
        """Sort collection by default."""
        return collection.order_by(*[
            sort.field.desc() if sort.meta['default'] == 'desc' else sort.field
            for sort in self.default
        ])
