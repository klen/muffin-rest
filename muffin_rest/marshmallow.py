from __future__ import annotations

from typing import TYPE_CHECKING

from marshmallow import Schema, ValidationError

from muffin_rest.errors import APIError

if TYPE_CHECKING:
    from collections.abc import Mapping


async def load_data(data: Mapping | list, schema: Schema | None = None, **params):
    if schema is None:
        return data

    try:
        return schema.load(data, many=isinstance(data, list), **params)
    except ValidationError as err:
        raise APIError.BAD_REQUEST("Bad request data", errors=err.messages) from err
