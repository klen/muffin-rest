"""Support filters for Mongo."""

import typing as t

from muffin_rest.filters import Filter, Filters


class MongoFilter(Filter):
    """Custom filter for sqlalchemy."""

    operators = {
        "$eq": lambda _, v: ("$eq", v),
        "$ge": lambda _, v: ("$ge", v),
        "$gt": lambda _, v: ("$gt", v),
        "$in": lambda _, v: ("$in", v),
        "$le": lambda _, v: ("$le", v),
        "$lt": lambda _, v: ("$lt", v),
        "$ne": lambda _, v: ("$ne", v),
        "$nin": lambda _, v: ("$nin", v),
        "$starts": lambda _, v: ("$regex", f"^{ v }"),
        "$ends": lambda _, v: ("$regex", f"{ v }$"),
    }

    async def filter(self, collection, *ops: t.Tuple[t.Callable, t.Any], **_):
        """Apply the filter."""
        return collection.find({self.field: dict(op(self.name, v) for op, v in ops)})


class MongoFilters(Filters):
    """Bind MongoFilter class."""

    MUTATE_CLASS = MongoFilter
