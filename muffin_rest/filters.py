"""Support API filters."""

from __future__ import annotations

import operator
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Iterable, Mapping, cast

import marshmallow as ma
from asgi_tools._compat import json_loads

from .utils import Mutate, Mutator

if TYPE_CHECKING:
    from muffin import Request

    from muffin_rest.types import TFilterOps, TFilterValue

    from .types import TVCollection

FILTERS_PARAM = "where"


class Filter(Mutate):
    """Base filter class."""

    operators: ClassVar[dict[str, Callable]] = {
        "$lt": operator.lt,
        "$le": operator.le,
        "$gt": operator.gt,
        "$ge": operator.ge,
        "$eq": operator.eq,
        "$ne": operator.ne,
        "$like": lambda v, c: c in v,
        # List ops
        "$in": lambda v, c: v in c,
        "$nin": lambda v, c: v not in c,
        # Logic ops
        "$or": lambda v, c: any(f(v, x) for f, x in c),
        "$and": lambda v, c: all(f(v, x) for f, x in c),
        "$not": lambda v, c: not all(f(v, x) for f, x in c),
        "$nor": lambda v, c: not any(f(v, x) for f, x in c),
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
        schema_field: ma.fields.Field | None = None,
        operator: str | None = None,
        **meta,
    ):
        """Initialize filter.

        :param name: The filter's name
        :param attr: Column/Property name.
        :param fields: Marshmallow Field instance

        """
        super(Filter, self).__init__(name, **meta)
        self.schema_field = schema_field or self.schema_field
        self.default_operator = operator or self.default_operator

    async def apply(self, collection: Any, data: Mapping | None = None, **ctx) -> tuple[Any, Any]:
        """Filter given collection."""
        if not data:
            return None, collection

        try:
            ops = self.parse(data)
        except ma.ValidationError:
            return None, collection

        if ops:
            collection = await self.filter(collection, *ops, **ctx)

        return ops, collection

    def condition(self, *ops: TFilterValue) -> Any:
        """Build a predicate from the given ops."""
        return lambda obj: all(op(get_value(obj, self.name), val) for op, val in ops)

    async def filter(self, collection: TVCollection, *ops: TFilterValue, **ctx) -> TVCollection:
        """Apply the filter to collection."""
        condition = self.condition(*ops)
        return cast("TVCollection", [item for item in collection if condition(item)])

    def parse(self, data: Mapping) -> TFilterOps:
        """Parse operator and value from filter's data."""
        value = data.get(self.name, ma.missing)
        return tuple(self._parse(value))

    def _parse(self, value) -> Iterable[TFilterValue]:
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


class MultiFilter(Filter):
    """Apply one filter to several names."""

    params: tuple[Any, ...]
    filters: dict[str, Filter]

    def __init__(self, name: str, *, filters: Iterable = (), **meta):
        """Initialize the filter."""
        super().__init__(name, **meta)
        self.params = tuple(filters)
        self.filters = {}

    async def apply(self, collection: Any, data: Mapping | None = None, **ctx):
        """Filter given collection."""
        values = data.get(self.name) if data else None
        if not isinstance(values, dict):
            return None, collection

        ops = {}
        for name, flt in self.filters.items():
            if name not in values:
                continue
            try:
                flt_ops = flt.parse(values)
            except ma.ValidationError:
                continue
            if flt_ops:
                ops[name] = flt_ops

        if not ops:
            return None, collection

        return ops, await self.filter(collection, ops, **ctx)

    async def filter(  # type: ignore[bad-override]
        self, collection: TVCollection, ops: Mapping[str, TFilterOps], **ctx
    ) -> TVCollection:
        """Apply child filters (AND by default)."""
        for name, flt_ops in ops.items():
            collection = await self.filters[name].filter(collection, *flt_ops, **ctx)
        return collection


class Filters(Mutator[Filter]):
    """Build filters for handlers."""

    MUTATE_CLASS = Filter
    mutations: Mapping[str, Filter]

    async def apply(
        self, request: Request, collection: TVCollection, **ctx
    ) -> tuple[TVCollection, dict[str, Any]]:
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
                        f = mutations[name]
                        ops, collection = await f.apply(collection, data=data, **ctx)
                        filters[name] = ops

            except (ValueError, TypeError, AssertionError):
                api = self.handler._api
                api.logger.warning("Invalid filters data: %s", request.url)

        return collection, filters

    def convert(self, obj, **meta):
        """Convert params to filters."""
        if isinstance(obj, MultiFilter):
            return self.convert_multi(obj)

        if isinstance(obj, self.MUTATE_CLASS):
            return obj

        field = meta.pop("field", None) or obj
        schema_field = meta.pop("schema_field", None)
        if schema_field is None and field:
            schema_field = self.handler.meta.Schema._declared_fields.get(field)
        return self.MUTATE_CLASS(obj, field=field, schema_field=schema_field, **meta)

    def convert_multi(self, multi: MultiFilter) -> MultiFilter:
        """Bind a single filter for each config entry."""
        for param in multi.params:
            obj, meta = param if isinstance(param, tuple) else (param, {})
            flt = self.convert(obj, **meta)
            if flt:
                multi.filters[flt.name] = flt
        return multi

    @property
    def openapi(self) -> dict:
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
