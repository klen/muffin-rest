"""Support API filters."""
import ujson
import operator

from cached_property import cached_property
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

    field_cls = fields.Raw

    def __init__(self, name, fname=None, field=None):
        """Initialize filter.

        :param name: Column/Property name.
        :param fname: Filter name
        :param fields: Marshmallow Field instance

        """
        self.field = field or self.field_cls()
        self.fname = fname or name
        self.name = name

    def __repr__(self):
        """String representation."""
        return '<Filter %s>' % self.name

    def parse(self, data):
        """Parse operator and value from filter's data."""
        val = data.get(self.fname, missing)
        if not isinstance(val, dict):
            return (self.operators['$eq'], self.field.deserialize(val)),

        return tuple(
            (
                self.operators[op],
                (self.field.deserialize(val)) if op != '$in' else [
                    self.field.deserialize(v) for v in val])
            for (op, val) in val.items() if op in self.operators
        )

    def filter(self, collection, data, resource=None, **kwargs):
        """Filter given collection."""
        ops = self.parse(data)
        validator = lambda obj: all(op(obj, val) for (op, val) in ops)  # noqa
        return [o for o in collection if validator(o)]


class Filters:

    """Build filters for given handler."""

    FILTER_CLASS = Filter

    def __init__(self, filters, Handler):
        """Initialize object."""
        self._filters = filters
        self.Handler = Handler

    @cached_property
    def filters(self):
        """Build filters."""
        if not self._filters:
            return None
        return list(f if isinstance(f, Filter) else self.convert(f) for f in self._filters)

    def convert(self, args):
        """Prepare filters."""
        name = args
        field = fname = None
        if isinstance(args, (list, tuple)):
            name, params = args
            field = params.get('field')
            fname = params.get('fname')

        if not self.Handler or  not self.Handler.Schema or \
                name not in self.Handler.Schema._declared_fields:
            return self.FILTER_CLASS(name, fname=fname, field=field)

        field = field or self.Handler.Schema._declared_fields[name]
        return self.FILTER_CLASS(name, fname=fname, field=field)

    def filter(self, data, collection, **kwargs):
        """Filter given collection."""
        if not data or self.filters is None:
            return collection

        for f in self.filters:
            if f.fname not in data:
                continue
            collection = f.filter(collection, data, resource=self.Handler, **kwargs)
        return collection
