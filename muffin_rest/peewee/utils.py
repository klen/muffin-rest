"""Support filters for Peewee ORM."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from warnings import warn

if TYPE_CHECKING:
    from peewee import Field


def get_model_field_by_name(handler, name: str, stacklevel=5) -> Optional[Field]:
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
