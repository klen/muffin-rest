from functools import partial

import marshmallow as ma
from marshmallow_peewee import DefaultConverter
from muffin_peewee.fields import IntEnumField, StrEnumField, URLField
from peewee import Model

from muffin_rest.peewee.utils import composite_key_to_id
from muffin_rest.schemas import EnumField


@DefaultConverter.register(StrEnumField)
@DefaultConverter.register(IntEnumField)
def build_field(field, opts, **params):
    params.pop("validate", None)
    return EnumField(field.enum, **params)


DefaultConverter.register(URLField, ma.fields.Url)


class CompositePKField(ma.fields.Field):
    """Support composite primary key as string."""

    def __init__(self, model: type[Model], **kwargs):
        pk = model._meta.primary_key  # type: ignore[]
        fields = [getattr(model, name) for name in pk.field_names]
        self.callable = partial(composite_key_to_id, fields)
        kwargs["dump_only"] = True
        super().__init__(**kwargs)

    def serialize(self, attr, obj, accessor=None, **kwargs):
        return self.callable(obj, None)

    def _serialize(self, value, attr, obj, **kwargs):
        return self.callable(obj, None)
