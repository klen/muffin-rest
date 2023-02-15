"""Implement a base class for API."""

import dataclasses as dc
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar, Union

import muffin
from http_router import Router
from muffin.utils import to_awaitable

from .openapi import render_openapi

AUTH = TypeVar("AUTH", bound=Callable[[muffin.Request], Awaitable])
REDOC_TEMPLATE = Path(__file__).parent.joinpath("redoc.html").read_text()
SWAGGER_TEMPLATE = Path(__file__).parent.joinpath("swagger.html").read_text()


@dc.dataclass
class API:
    """Initialize an API."""

    def __init__(
        self,
        app: Optional[muffin.Application] = None,
        prefix: str = "",
        openapi: bool = True,
        *,
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

        self.authorize: Callable[[muffin.Request], Awaitable] = to_awaitable(
            lambda _: True
        )
        self.router = Router()

        if app:
            self.setup(app, prefix=prefix)

    def __repr__(self):
        """Stringify the API."""
        return f"<API { self.prefix }>"

    def authorization(self, auth: AUTH) -> AUTH:
        """Bind an authorization flow to self API."""
        self.authorize = auth
        return auth

    @property
    def logger(self):
        """Proxy the application's logger."""
        if self.app is None:
            raise RuntimeError("API must be binded to an app.")

        return self.app.logger

    def setup(
        self,
        app: muffin.Application,
        prefix: str = "",
        openapi: Optional[bool] = None,
        *,
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

    def route(self, path: Union[str, Any], *paths: str, **params):
        """Route an endpoint by the API."""
        from .handler import RESTBase

        def wrapper(cb):
            cb._api = self
            return self.router.route(*paths, **params)(cb)

        if isinstance(path, str):
            paths = (path, *paths)
            return wrapper

        # Generate URL paths automatically
        if issubclass(path, RESTBase):
            path._api = self
            return self.router.route(path, *paths, **params)

        raise Exception("Invalid endpoint")  # TODO


async def swagger(_):
    """Get the Swagger UI."""
    return SWAGGER_TEMPLATE


async def redoc(_):
    """Get the ReDoc UI."""
    return REDOC_TEMPLATE
