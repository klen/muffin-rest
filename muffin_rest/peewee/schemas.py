import marshmallow as ma
from marshmallow_peewee import DefaultConverter
from muffin_peewee.fields import IntEnumField, StrEnumField


class EnumField(ma.fields.Field):
    default_error_messages = {
        "unknown": "Must be one of: {choices}.",
    }

    def __init__(self, enum, **kwargs):
        self.enum = enum
        self.choices_text = ", ".join([str(c.value) for c in enum])
        super().__init__(**kwargs)

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None

        return value.value

    def _deserialize(self, value, attr, data, **kwargs):
        try:
            return self.enum(value)
        except ValueError as error:
            raise self.make_error("unknown", choices=self.choices_text) from error


@DefaultConverter.register(StrEnumField)
@DefaultConverter.register(IntEnumField)
def build_field(field, opts, **params):
    params.pop("validate", None)
    return EnumField(field.enum, **params)


# ruff: noqa: ARG001, ARG002
