"""Support API filters."""
import operator
import typing as t

import marshmallow as ma


class Filter:

    """Base filter class."""

    operators = {
        '<':   operator.lt,
        '$lt': operator.lt,
        '<=':  operator.le,
        '$le': operator.le,
        '>':   operator.gt,
        '$gt': operator.gt,
        '>=':  operator.ge,
        '$ge': operator.ge,
        '==':  operator.eq,
        '$eq': operator.eq,
        '!':   operator.ne,
        '$ne': operator.ne,
        '$in': lambda v, c: v in c,
        '$nin': lambda v, c: v not in c,
    }
    operators['<<'] = operators['$in']

    list_ops = ['$in', '<<']

    field_cls: t.Type[ma.fields.Field] = ma.fields.Raw

    def __init__(self, name: str, attr: str = None, field: ma.fields.Field = None):
        """Initialize filter.

        :param name: The filter's name
        :param attr: Column/Property name.
        :param fields: Marshmallow Field instance

        """
        self.name = name
        self.attr = attr or name
        self.field = field or self.field_cls(attribute=self.attr)

    def __repr__(self) -> str:
        """Represent self as a string."""
        return '<Filter %s>' % self.name

    def filter(self, collection: t.Any, data: t.Mapping, **kwargs):
        """Filter given collection."""
        try:
            ops = self.parse(data)
        except ma.ValidationError:
            return None, collection

        collection = self.apply(collection, ops, **kwargs)
        return ops, collection

    def parse(self, data: t.Mapping) -> t.Tuple[t.Tuple[t.Callable, t.Any], ...]:
        """Parse operator and value from filter's data."""
        val = data.get(self.name, ma.missing)
        if not isinstance(val, dict):
            return (self.operators['$eq'], self.field.deserialize(val)),

        return tuple(
            (
                self.operators[op],
                (self.field.deserialize(val)) if op not in self.list_ops else [
                    self.field.deserialize(v) for v in val])
            for (op, val) in val.items() if op in self.operators
        )

    def apply(self, collection, ops, **kwargs):
        """Apply the filter to collection."""
        validator = lambda obj: all(op(get_value(obj, self.name), val) for (op, val) in ops)  # noqa
        return [o for o in collection if validator(o)]


class Filters:

    """Build filters for given endpoint."""

    FILTER_CLASS = Filter

    def __init__(self, *filters, endpoint=None):
        """Initialize object."""
        self.filters = tuple(
            f if isinstance(f, Filter) else self.convert(f, endpoint) for f in filters)

    def __iter__(self):
        """Iterate through self filters."""
        return iter(self.filters)

    def __str__(self) -> str:
        """Describe the filters."""
        return ", ".join(f.name for f in self)

    def convert(self, args, endpoint=None):
        """Prepare filters."""
        name = args
        field = attr = None
        opts = ()
        if isinstance(args, (list, tuple)):
            name, *opts = args
            if opts:
                attr = opts.pop()
            if opts:
                field = opts.pop()

        if not field and endpoint and endpoint.meta.Schema:
            field = endpoint.meta.Schema._declared_fields.get(attr or name) or \
                self.FILTER_CLASS.field_cls()
            field.attribute = field.attribute or attr or name
        return self.FILTER_CLASS(name, attr=attr, field=field, *opts)

    def filter(self, data, collection, **kwargs):
        """Filter given collection."""
        if not data or self.filters is None:
            return None, collection

        filters = {}
        for f in self.filters:
            if f.name not in data:
                continue
            ops, collection = f.filter(collection, data, **kwargs)
            filters[f.name] = ops

        return filters, collection


def get_value(obj, name):
    """Get value from object by name."""
    if isinstance(obj, dict):
        return obj.get(name)

    return getattr(obj, name, obj)
