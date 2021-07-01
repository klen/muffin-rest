"""Support filters for Mongo."""

import typing as t

from ..filters import Filter, Filters


class MongoFilter(Filter):
    """Custom filter for sqlalchemy."""

    operators = {
        '$eq': lambda n, v: ('$eq', v),
        '$ge': lambda n, v: ('$ge', v),
        '$gt': lambda n, v: ('$gt', v),
        '$in': lambda n, v: ('$in', v),
        '$le': lambda n, v: ('$le', v),
        '$lt': lambda n, v: ('$lt', v),
        '$ne': lambda n, v: ('$ne', v),
        '$nin': lambda n, v: ('$nin', v),
        '$starts': lambda n, v: ('$regex', f"^{ v }"),
        '$ends': lambda n, v: ('$regex', f"{ v }$"),
    }

    def apply(self, collection, *ops: t.Tuple[t.Callable, t.Any], **options):
        """Apply the filter."""
        return collection.find({self.field: dict(op(self.name, v) for op, v in ops)})


class MongoFilters(Filters):
    """Bind MongoFilter class."""

    MUTATE_CLASS = MongoFilter
