import marshmallow as ma


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

        try:
            return value.value
        except AttributeError:
            raise ma.ValidationError(f"{obj}: {attr} value is invalid: {value}") from None

    def _deserialize(self, value, attr, data, **kwargs):
        try:
            return self.enum(value)
        except ValueError as error:
            raise self.make_error("unknown", choices=self.choices_text) from error
