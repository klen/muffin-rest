"""Serialize/deserialize results from mongo db."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import bson
import marshmallow as ma

if TYPE_CHECKING:
    from collections.abc import Mapping


class ObjectId(ma.fields.Field):
    """ObjectID Marshmallow Field."""

    def _deserialize(
        self,
        value: Any,
        attr: str | None,
        data: Mapping[str, Any] | None,
        **kwargs: Any,
    ) -> Any:
        try:
            return bson.ObjectId(value)
        except ValueError as exc:
            raise ma.ValidationError("invalid ObjectId `%s`" % value) from exc

    def _serialize(self, value: Any, attr: str | None, obj: Any, **kwargs: Any) -> Any:
        if value is None:
            return ma.missing
        return str(value)


class MongoSchema(ma.Schema):
    """Serialize/deserialize results from mongo."""

    _id = ObjectId()

    def __init__(self, instance: Any = None, **kwargs: Any) -> None:
        """Initialize the schema."""
        self.instance = instance
        super(MongoSchema, self).__init__(**kwargs)

    @ma.post_load
    def make_instance(self, data: Any, **__: Any) -> Any:
        """Build object from data."""
        if self.instance is not None:
            self.instance.update(data)
            return self.instance

        return data

    def load(self, data: Any, instance: Any = None, *args: Any, **kwargs: Any) -> Any:
        """Load data."""
        self.instance = instance or self.instance
        return super(MongoSchema, self).load(data, *args, **kwargs)
