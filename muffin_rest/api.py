"""Implement a base class for API."""

from __future__ import annotations

import dataclasses as dc
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union, overload

from http_router import Router
from muffin.utils import TV, to_awaitable

from .errors import InvalidEnpointError
from .openapi import render_openapi

if TYPE_CHECKING:
    import muffin

    from muffin_rest.types import TAuth, TVAuth, TVHandler

REDOC_TEMPLATE = Path(__file__).parent.joinpath("redoc.html").read_text()
SWAGGER_TEMPLATE = Path(__file__).parent.joinpath("swagger.html").read_text()


@dc.dataclass
class API:
    """Initialize an API."""

    def __init__(
        self,
        app: Optional[muffin.Application] = None,
        prefix: str = "",
        *,
        openapi: bool = True,
        servers: Optional[List] = None,
        **openapi_info,
    ):
        """Post initialize the API if we have an application already."""
        self.app = app
        self.prefix = prefix

        self.openapi = openapi
        self.openapi_options: Dict[str, Any] = {"info": openapi_info}
        if servers:
            self.openapi_options["servers"] = servers

        self.authorize: TAuth = to_awaitable(lambda _: True)
        self.router = Router()

        if app:
            self.setup(app, prefix=prefix)

    def __repr__(self):
        """Stringify the API."""
        return f"<API { self.prefix }>"

    @property
    def logger(self):
        """Proxy the application's logger."""
        if self.app is None:
            raise RuntimeError("API is not initialized yet")

        return self.app.logger

    def setup(
        self,
        app: muffin.Application,
        *,
        prefix: str = "",
        openapi: Optional[bool] = None,
        servers: Optional[List] = None,
        **openapi_info,
    ):
        """Initialize the API."""
        self.app = app
        self.prefix = (prefix or self.prefix).rstrip("/")

        # Setup routing
        self.router.trim_last_slash = self.app.router.trim_last_slash
        self.router.validator = self.app.router.validator
        self.app.router.route(self.prefix)(self.router)

        if openapi is not None:
            self.openapi = openapi

        if openapi_info:
            self.openapi_options["info"] = openapi_info

        if servers:
            self.openapi_options["servers"] = servers

        # Setup API Docs
        if not self.openapi:
            return

        async def openapi_json(request):
            return render_openapi(self, request=request)

        self.router.route("/swagger")(swagger)
        self.router.route("/redoc")(redoc)
        self.router.route("/openapi.json")(openapi_json)

    @overload
    def route(self, obj: str, *paths: str, **params) -> Callable[[TV], TV]:
        ...

    @overload
    def route(self, obj: TVHandler, *paths: str, **params) -> TVHandler:
        ...

    def route(
        self, obj: Union[str, TVHandler], *paths: str, **params
    ) -> Union[Callable[[TV], TV], TVHandler]:
        """Route an endpoint by the API."""
        from .handler import RESTBase

        def wrapper(cb):
            cb._api = self
            return self.router.route(*paths, **params)(cb)

        if isinstance(obj, str):
            paths = (obj, *paths)
            return wrapper

        # Generate URL paths automatically
        if issubclass(obj, RESTBase):
            obj._api = self
            return self.router.route(*paths, **params)(obj)

        raise InvalidEnpointError

    def authorization(self, auth: TVAuth) -> TVAuth:
        """Bind an authorization flow to self API."""
        self.authorize = auth
        return auth


async def swagger(_) -> str:
    """Get the Swagger UI."""
    return SWAGGER_TEMPLATE


async def redoc(_) -> str:
    """Get the ReDoc UI."""
    return REDOC_TEMPLATE
