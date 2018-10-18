"""Support API filters."""
import operator

from marshmallow import fields, missing


class Filter:

    """Base filter class."""

    operators = {
        '$lt': operator.lt,
        '$le': operator.le,
        '$gt': operator.gt,
        '$ge': operator.ge,
        '$eq': operator.eq,
        '$ne': operator.ne,
        '$in': lambda v, c: v in c,
    }

    list_ops = '$in',

    field_cls = fields.Raw

    def __init__(self, name, attr=None, field=None):
        """Initialize filter.

        :param name: The filter's name
        :param attr: Column/Property name.
        :param fields: Marshmallow Field instance

        """
        self.name = name
        self.attr = attr or name
        self.field = field or self.field_cls(attribute=self.attr)

    def __repr__(self):
        """String representation."""
        return '<Filter %s>' % self.name

    def filter(self, collection, data, **kwargs):
        """Filter given collection."""
        ops = self.parse(data)
        collection = self.apply(collection, ops, **kwargs)
        return ops, collection

    def parse(self, data):
        """Parse operator and value from filter's data."""
        val = data.get(self.name, missing)
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
        validator = lambda obj: all(op(obj, val) for (op, val) in ops)  # noqa
        return [o for o in collection if validator(o)]


class Filters:

    """Build filters for given handler."""

    FILTER_CLASS = Filter

    def __init__(self, *filters, handler=None):
        """Initialize object."""
        self.filters = tuple(
            f if isinstance(f, Filter) else self.convert(f, handler) for f in filters)

    def convert(self, args, handler=None):
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

        if not field and handler and handler.Schema:
            field = handler.Schema._declared_fields.get(attr or name) or \
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
