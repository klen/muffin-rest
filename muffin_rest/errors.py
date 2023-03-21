"""Helpers to raise API errors as JSON responses."""
from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING, Dict, Optional

from muffin import ResponseError

if TYPE_CHECKING:
    from asgi_tools.types import TJSON


class APIError(ResponseError):
    """JSON Response."""

    def __init__(
        self,
        content: Optional[TJSON] = None,
        *,
        status_code: int = HTTPStatus.BAD_REQUEST.value,
        **json_data,
    ):
        """Create JSON with errors information."""
        response = {"error": True, "message": HTTPStatus(status_code).description}

        if isinstance(content, Dict):
            response = content

        elif content is not None:
            response["message"] = str(content)

        if json_data:
            response.update(json_data)

        super(APIError, self).__init__(
            json.dumps(response),
            status_code=status_code,
            headers={"content-type": "application/json"},
        )


class InvalidEnpointError(TypeError):
    """Invalid endpoint."""


class HandlerNotBindedError(RuntimeError):
    """Handler not binded."""
