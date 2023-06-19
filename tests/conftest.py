from json import dumps
from typing import Any, Dict, Optional, Tuple, Union

import muffin
import pytest
from asgi_tools.tests import ASGITestClient

from muffin_rest.filters import FILTERS_PARAM
from muffin_rest.sorting import SORT_PARAM


@pytest.fixture(
    params=[
        pytest.param(("asyncio", {"use_uvloop": False}), id="asyncio"),
        pytest.param("trio"),
        pytest.param("curio"),
    ],
    autouse=True,
)
def aiolib(request):
    return request.param


@pytest.fixture()
def app():
    app = muffin.Application(debug=True)

    @app.route("/")
    async def index(_):
        return "OK"

    return app


@pytest.fixture()
async def api(app):
    from muffin_rest import API

    return API(app, "/api")


@pytest.fixture()
def apiclient(app):
    return APITestClient(app)


class APITestClient(ASGITestClient):
    """Support auth and filters."""

    async def request(  # noqa: PLR0913
        self,
        path: str,
        method: str = "GET",
        *,
        filters: Optional[Dict[str, Any]] = None,
        sort: Union[Tuple[str, ...], str, None] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        **kwargs,
    ):
        kwargs.setdefault("query", {})
        if filters:
            kwargs["query"][FILTERS_PARAM] = dumps(filters)

        if sort:
            kwargs["query"][SORT_PARAM] = ",".join(sort) if isinstance(sort, tuple | list) else sort

        if limit is not None:
            kwargs["query"]["limit"] = str(limit)

        if offset is not None:
            kwargs["query"]["offset"] = str(offset)

        return await super().request(path, method, **kwargs)
