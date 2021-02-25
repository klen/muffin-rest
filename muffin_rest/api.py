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

    app: t.Optional[muffin.Application] = dc.field(default=None, repr=False)
    prefix: str = ''
    apispec: bool = True
    apispec_params: t.Dict[str, t.Any] = dc.field(default_factory=dict, repr=False)
    router: Router = dc.field(default_factory=Router, repr=False)

    def __post_init__(self):
        """Post initialize the API if we have an application already."""
        if self.app:
            self.setup(self.app, prefix=self.prefix)
        self.authorize: t.Callable[[muffin.Request], t.Awaitable] = to_awaitable(lambda r: True)

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
              apispec: bool = None, apispec_params: t.Dict[str, t.Any] = None):
        """Initialize the API."""
        self.app = app
        self.prefix = prefix.rstrip('/')

        if apispec is not None:
            self.apispec = apispec

        if apispec_params is not None:
            self.apispec_params = apispec_params

        # Setup routing
        self.router.trim_last_slash = self.app.router.trim_last_slash
        self.router.validate_cb = self.app.router.validate_cb               # type: ignore
        self.router.MethodNotAllowed = self.app.router.MethodNotAllowed     # type: ignore
        self.router.NotFound = self.app.router.NotFound                     # type: ignore
        self.app.router.route(self.prefix)(self.router)

        # Setup API Docs
        if not self.apispec:
            return

        @self.router.route('/swagger')
        async def swagger(request):
            return SWAGGER_TEMPLATE

        @self.router.route('/redoc')
        async def redoc(request):
            return REDOC_TEMPLATE

        self.apispec_params.setdefault('openapi_version', "3.0.2")
        self.apispec_params.setdefault('title', f"{ app.name.title() } API")
        self.apispec_params.setdefault('version', "1.0.0")

        @self.router.route('/openapi.json')
        async def openapi(request):
            return render_openapi(self, request=request)

    def route(self, path: t.Union[str, t.Any], *paths: str, **params):
        """Route an endpoint by the API."""
        from .endpoint import Endpoint

        def wrapper(cb):
            cb._api = self
            return self.router.route(*paths, **params)(cb)

        if isinstance(path, str):
            paths = (path, *paths)
            return wrapper

        # Generate URL paths automatically
        if issubclass(path, Endpoint):
            path._api = self
            return self.router.route(path, *paths, **params)

        raise Exception("Invalid endpoint")  # TODO
