"""Support filters for Peewee ORM."""

from __future__ import annotations

from typing import TYPE_CHECKING
from warnings import warn

if TYPE_CHECKING:
    from peewee import CompositeKey, Field


def get_model_field_by_name(handler, name: str, *, stacklevel=5) -> Field | None:
    """Get model field by name."""
    fields = handler.meta.model._meta.fields
    candidate = fields.get(name)
    if candidate:
        return candidate

    for field in fields.values():
        if field.column_name == name:
            return field

    warn(
        f"{handler.__qualname__} {handler.meta.model} has no field {name}",
        category=RuntimeWarning,
        stacklevel=stacklevel,
    )
    return None


SEPARATOR = "::"


def composite_key_to_id(fields: list[Field], instance, _) -> str:
    """Convert composite key to string id."""
    return SEPARATOR.join(str(field.db_value(getattr(instance, field.name))) for field in fields)


def id_to_composite_keys(pk: CompositeKey, id_: str) -> dict[str, str]:
    """Convert string id to composite key."""
    values = id_.split(SEPARATOR)
    if len(values) != len(pk.field_names):
        raise ValueError("Invalid id")
    return dict(zip(pk.field_names, values, strict=True))
