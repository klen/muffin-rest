from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import marshmallow as ma

if TYPE_CHECKING:
    from collections.abc import Mapping


class EnumField(ma.fields.Field):
    default_error_messages: ClassVar = {  # type: ignore[misc]
        "unknown": "Must be one of: {choices}.",
    }

    def __init__(self, enum: Any, *, by_value: bool = True, **kwargs: Any) -> None:
        self.enum = enum
        self.by_value = by_value
        self.choices_text = ", ".join([str(c.value) for c in enum])
        super().__init__(**kwargs)

    def _serialize(self, value: Any, attr: str | None, obj: Any, **kwargs: Any) -> Any:
        if value is None:
            return None

        try:
            return value.value if self.by_value else value.name
        except AttributeError:
            raise ma.ValidationError(f"{obj}: {attr} value is invalid: {value}") from None

    def _deserialize(
        self,
        value: Any,
        attr: str | None,
        data: Mapping[str, Any] | None,
        **kwargs: Any,
    ) -> Any:
        try:
            return self.enum(value) if self.by_value else self.enum[value]
        except (ValueError, KeyError) as error:
            raise self.make_error("unknown", choices=self.choices_text) from error
