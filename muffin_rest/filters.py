"""Support API filters."""
from __future__ import annotations

import operator
from typing import TYPE_CHECKING, Any, Callable, Dict, Mapping, Optional, Tuple, Type

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
        "<": operator.lt,
        "$lt": operator.lt,
        "<=": operator.le,
        "$le": operator.le,
        ">": operator.gt,
        "$gt": operator.gt,
        ">=": operator.ge,
        "$ge": operator.ge,
        "==": operator.eq,
        "$eq": operator.eq,
        "!": operator.ne,
        "$ne": operator.ne,
        "$in": operator.contains,
        "$nin": lambda v, c: v not in c,
    }
    operators["<<"] = operators["$in"]

    list_ops = ["$in", "<<"]

    schema_field_cls: Type[ma.fields.Field] = ma.fields.Raw
    default_operator: str = "$eq"

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
        self.field = field
        self.schema_field = schema_field or self.schema_field_cls()
        if operator:
            self.default_operator = operator

    async def apply(self, collection: Any, data: Optional[Mapping] = None, **kwargs):
        """Filter given collection."""
        if not data:
            return None, collection

        try:
            ops = self.parse(data)
        except ma.ValidationError:
            return None, collection

        if ops:
            collection = await self.filter(collection, *ops, **kwargs)

        return ops, collection

    async def filter(self, collection, *ops: Tuple[Callable, Any], **_):
        """Apply the filter to collection."""

        def validator(obj):
            return all(op(get_value(obj, self.name), val) for op, val in ops)

        return [o for o in collection if validator(o)]

    def parse(self, data: Mapping) -> Tuple[Tuple[Callable, Any], ...]:
        """Parse operator and value from filter's data."""
        val = data.get(self.name, ma.missing)
        if not isinstance(val, dict):
            return (
                (
                    self.operators[self.default_operator],
                    self.schema_field.deserialize(val),
                ),
            )

        return tuple(
            (
                self.operators[op],
                (self.schema_field.deserialize(val))
                if op not in self.list_ops
                else [self.schema_field.deserialize(v) for v in val],
            )
            for (op, val) in val.items()
            if op in self.operators
        )


class Filters(Mutator):

    """Build filters for handlers."""

    MUTATE_CLASS = Filter
    mutations: Mapping[str, Filter]

    async def apply(
        self,
        request: Request,
        collection: TVCollection,
        **options,
    ) -> TVCollection:
        """Filter the given collection."""
        data = request.url.query.get(FILTERS_PARAM)
        if data is not None:
            try:
                data = json_loads(data)
                assert isinstance(data, dict)
                mutations = self.mutations
                for name in data:
                    if name in mutations:
                        _, collection = await mutations[name].apply(
                            collection,
                            data,
                            **options,
                        )

            except (ValueError, TypeError, AssertionError):
                api = self.handler._api
                api.logger.warning("Invalid filters data: %s", request.url)

        return collection

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
