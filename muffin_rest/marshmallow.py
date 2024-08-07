from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Optional, Union, cast

from marshmallow import Schema, ValidationError

from muffin_rest.errors import APIError

if TYPE_CHECKING:
    from asgi_tools import Request


async def load_data(request: Request, schema: Optional[Schema] = None, **params):
    try:
        data = await request.data(raise_errors=True)
    except (ValueError, TypeError) as err:
        raise APIError.BAD_REQUEST(str(err)) from err

    if schema is None:
        return data

    try:
        return schema.load(cast(Union[Mapping, list], data), many=isinstance(data, list), **params)
    except ValidationError as err:
        raise APIError.BAD_REQUEST("Bad request data", errors=err.messages) from err
