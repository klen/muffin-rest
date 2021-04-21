"""Implement a base class for API."""

import dataclasses as dc
import typing as t
from pathlib import Path

import muffin
from http_router import Router
from muffin.utils import to_awaitable

from .openapi import render_openapi


AUTH = t.TypeVar('AUTH', bound=t.Callable[[muffin.Request], t.Awaitable])
REDOC_TEMPLATE = Path(__file__).parent.joinpath('redoc.html').read_text()
SWAGGER_TEMPLATE = Path(__file__).parent.joinpath('swagger.html').read_text()


@dc.dataclass
class API:
    """Initialize an API."""

    def __init__(self, app: muffin.Application = None, prefix: str = '',
                 openapi: bool = True, *, servers: t.List = None, **openapi_info):
        """Post initialize the API if we have an application already."""
        self.app = app
        self.prefix = prefix

        self.openapi = openapi
        self.openapi_options: t.Dict[str, t.Any] = {'info': openapi_info}
        if servers:
            self.openapi_options['servers'] = servers

        self.authorize: t.Callable[[muffin.Request], t.Awaitable] = to_awaitable(lambda r: True)
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
            raise RuntimeError('API must be binded to an app.')

        return self.app.logger

    def setup(self, app: muffin.Application, prefix: str = '',
              openapi: bool = None, *, servers: t.List = None, **openapi_info):
        """Initialize the API."""
        self.app = app
        self.prefix = (prefix or self.prefix).rstrip('/')

        # Setup routing
        self.router.trim_last_slash = self.app.router.trim_last_slash
        self.router.validator = self.app.router.validator                   # type: ignore
        self.app.router.route(self.prefix)(self.router)

        if openapi is not None:
            self.openapi = openapi

        if openapi_info:
            self.openapi_options['info'] = openapi_info

        if servers:
            self.openapi_options['servers'] = servers

        # Setup API Docs
        if not self.openapi:
            return

        @self.router.route('/swagger')
        async def swagger(request):
            return SWAGGER_TEMPLATE

        @self.router.route('/redoc')
        async def redoc(request):
            return REDOC_TEMPLATE

        @self.router.route('/openapi.json')
        async def openapi_json(request):
            return render_openapi(self, request=request)

    def route(self, path: t.Union[str, t.Any], *paths: str, **params):
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
