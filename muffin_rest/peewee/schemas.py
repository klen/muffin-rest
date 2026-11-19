from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any

import marshmallow as ma
from marshmallow_peewee import DefaultConverter
from muffin_peewee.fields import IntEnumField, StrEnumField, URLField

from muffin_rest.peewee.utils import composite_key_to_id
from muffin_rest.schemas import EnumField

if TYPE_CHECKING:
    from peewee import Model


@DefaultConverter.register(StrEnumField)
@DefaultConverter.register(IntEnumField)
def build_field(field: Any, opts: Any, **params: Any) -> EnumField:
    params.pop("validate", None)
    return EnumField(field.enum, **params)


DefaultConverter.register(URLField, ma.fields.Url)


class CompositePKField(ma.fields.Field):
    """Support composite primary key as string."""

    def __init__(self, model: type[Model], **kwargs: Any) -> None:
        pk = model._meta.primary_key  # type: ignore[]
        fields = [getattr(model, name) for name in pk.field_names]  # pyrefly: ignore[missing-attribute]
        self.callable = partial(composite_key_to_id, fields)
        kwargs["dump_only"] = True
        super().__init__(**kwargs)

    def serialize(self, attr: str, obj: Any, accessor: Any = None, **kwargs: Any) -> str:
        return self.callable(obj, None)

    def _serialize(self, value: Any, attr: str | None, obj: Any, **kwargs: Any) -> str:
        return self.callable(obj, None)
