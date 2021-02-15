"""Serialize/deserialize results from mongo db."""

import marshmallow as ma
import bson


class ObjectId(ma.fields.Field):

    """ObjectID Marshmallow Field."""

    def _deserialize(self, value, attr, data):
        try:
            return bson.ObjectId(value)
        except ValueError:
            raise ma.ValidationError('invalid ObjectId `%s`' % value)

    def _serialize(self, value, attr, obj):
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
    def make_instance(self, data, **kwargs):
        """Build object from data."""
        if self.instance is not None:
            self.instance.update(data)
            return self.instance

        return data

    def load(self, data, instance=None, *args, **kwargs):
        """Load data."""
        self.instance = instance or self.instance
        return super(MongoSchema, self).load(data, *args, **kwargs)
