"""Serialize/deserialize results from mongo db."""

import bson
import marshmallow as ma


class ObjectId(ma.fields.Field):

    """ObjectID Marshmallow Field."""

    def _deserialize(self, value, _, __):
        try:
            return bson.ObjectId(value)
        except ValueError as exc:
            raise ma.ValidationError("invalid ObjectId `%s`" % value) from exc

    def _serialize(self, value, _, __):
        if value is None:
            return ma.missing
        return str(value)


class MongoSchema(ma.Schema):

    """Serialize/deserialize results from mongo."""

    _id = ObjectId()

    def __init__(self, instance=None, **kwargs):
        """Initialize the schema."""
        self.instance = instance
        super(MongoSchema, self).__init__(**kwargs)

    @ma.post_load
    def make_instance(self, data, **__):
        """Build object from data."""
        if self.instance is not None:
            self.instance.update(data)
            return self.instance

        return data

    def load(self, data, instance=None, *args, **kwargs):
        """Load data."""
        self.instance = instance or self.instance
        return super(MongoSchema, self).load(data, *args, **kwargs)
