import marshmallow as ma
from marshmallow_peewee import DefaultConverter
from muffin_peewee.fields import IntEnumField, StrEnumField, URLField

from muffin_rest.schemas import EnumField


@DefaultConverter.register(StrEnumField)
@DefaultConverter.register(IntEnumField)
def build_field(field, opts, **params):
    params.pop("validate", None)
    return EnumField(field.enum, **params)


DefaultConverter.register(URLField, ma.fields.Url)

# ruff: noqa: ARG001, ARG002
