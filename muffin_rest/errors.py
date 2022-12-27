"""Helpers to raise API errors as JSON responses."""
import json
from http import HTTPStatus
from typing import Mapping, Union

from muffin import ResponseError
from muffin.typing import JSONType


class APIError(ResponseError):
    """JSON Response."""

    def __init__(
        self,
        content: Union[str, JSONType] = None,
        *,
        status_code: int = HTTPStatus.BAD_REQUEST.value,
        **json_data
    ):
        """Create JSON with errors information."""
        response = {"error": True, "message": HTTPStatus(status_code).description}

        if isinstance(content, Mapping):
            response = content

        elif content is not None:
            response["message"] = str(content)

        if json_data:
            response.update(json_data)

        return super(APIError, self).__init__(
            json.dumps(response),
            status_code=status_code,
            headers={"content-type": "application/json"},
        )
