"""Support API filters."""
from __future__ import annotations

import operator
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Mapping, Optional, Tuple  # py38

import marshmallow as ma
from asgi_tools._compat import json_loads  # type: ignore[]

from .utils import Mutate, Mutator

if TYPE_CHECKING:
    from muffin import Request

    from .types import TVCollection

FILTERS_PARAM = "where"


class Filter(Mutate):
    """Base filter class."""

    operators: Dict[str, Callable] = {
        "$lt": operator.lt,
        "$le": operator.le,
        "$gt": operator.gt,
        "$ge": operator.ge,
        "$eq": operator.eq,
        "$ne": operator.ne,
        "$like": lambda v, c: c in v,
        # List ops
        "$in": operator.contains,
        "$nin": lambda v, c: v not in c,
        # Logic ops
        "$or": lambda v, c: any(f(v, c) for f in v),
        "$and": lambda v, c: all(f(v, c) for f in v),
        "$not": lambda v, c: not v(c),
        "$nor": lambda v, c: not any(f(v, c) for f in v),
    }
    operators["<"] = operators["$lt"]
    operators["<="] = operators["$lte"] = operators["$le"]
    operators[">"] = operators["$gt"]
    operators[">="] = operators["$gte"] = operators["$ge"]
    operators["=="] = operators["$eq"]
    operators["!="] = operators["$ne"]
    operators["<<"] = operators["$in"]

    list_ops: Iterable[str] = ("$in", "<<", "$nin")
    logic_ops: Iterable[str] = ("$or", "$and", "$not", "$nor")

    schema_field: ma.fields.Field = ma.fields.Raw()
    default_operator = "$eq"

    def __init__(
        self,
        name: str,
        *,
        field: Any = None,
        schema_field: Optional[ma.fields.Field] = None,
        operator: Optional[str] = None,
        **meta,
    ):
        """Initialize filter.

        :param name: The filter's name
        :param attr: Column/Property name.
        :param fields: Marshmallow Field instance

        """
        super(Filter, self).__init__(name, **meta)
        self.field = field if field is not None else self.field
        self.schema_field = schema_field or self.schema_field
        self.default_operator = operator or self.default_operator

    async def apply(self, collection: Any, data: Optional[Mapping] = None):
        """Filter given collection."""
        if not data:
            return None, collection

        try:
            ops = self.parse(data)
        except ma.ValidationError:
            return None, collection

        if ops:
            collection = await self.filter(collection, *ops)

        return ops, collection

    async def filter(self, collection, *ops: Tuple[Callable, Any], **_):
        """Apply the filter to collection."""

        def validator(obj):
            return all(op(get_value(obj, self.name), val) for op, val in ops)

        return [item for item in collection if validator(item)]

    def parse(self, data: Mapping):
        """Parse operator and value from filter's data."""
        value = data.get(self.name, ma.missing)
        return tuple(self._parse(value))

    def _parse(self, value):
        deserialize = self.schema_field.deserialize
        if isinstance(value, dict):
            for op, val in value.items():
                operator = self.operators.get(op)
                if operator is None:
                    continue

                if op in self.list_ops:
                    yield operator, [deserialize(v) for v in val]

                elif op in self.logic_ops:
                    yield operator, [t for v in val for t in tuple(self._parse(v))]

                else:
                    yield operator, deserialize(val)

        else:
            yield (self.operators[self.default_operator], deserialize(value))


class Filters(Mutator):
    """Build filters for handlers."""

    MUTATE_CLASS = Filter
    mutations: Mapping[str, Filter]

    async def apply(
        self, request: Request, collection: TVCollection
    ) -> Tuple[TVCollection, Dict[str, Any]]:
        """Filter the given collection."""
        raw_data = request.url.query.get(FILTERS_PARAM)
        filters = {}
        if raw_data is not None:
            try:
                data = json_loads(raw_data)
                assert isinstance(data, dict)
                mutations = self.mutations
                for name in mutations:
                    if name in data:
                        ops, collection = await mutations[name].apply(collection, data)
                        filters[name] = ops

            except (ValueError, TypeError, AssertionError):
                api = self.handler._api
                api.logger.warning("Invalid filters data: %s", request.url)

        return collection, filters

    def convert(self, obj, **meta):
        """Convert params to filters."""
        if isinstance(obj, self.MUTATE_CLASS):
            return obj

        field = meta.pop("field", None) or obj
        schema_field = meta.pop("schema_field", None)
        if schema_field is None and field:
            schema_field = self.handler.meta.Schema._declared_fields.get(field)
        return self.MUTATE_CLASS(obj, field=field, schema_field=schema_field, **meta)

    @property
    def openapi(self) -> Dict:
        """Prepare OpenAPI params."""
        return {
            "name": FILTERS_PARAM,
            "in": "query",
            "description": str(self),
            "content": {"application/json": {"schema": {"type": "object"}}},
        }


def get_value(obj, name: str):
    """Get value from object by name."""
    if isinstance(obj, dict):
        return obj.get(name)

    return getattr(obj, name, obj)
