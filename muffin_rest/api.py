"""Implement a base class for API."""

import dataclasses as dc
import typing as t

import muffin
from muffin.utils import to_awaitable
from http_router import Router


AUTH = t.TypeVar('AUTH', bound=t.Callable[[muffin.Request], t.Awaitable])


@dc.dataclass
class API:
    """Initialize an API."""

    app: t.Optional[muffin.Application] = dc.field(default=None, repr=False)
    prefix: str = ''
    router: Router = dc.field(default_factory=Router, repr=False)

    def __post_init__(self):
        """Post initialize the API if we have an application already."""
        if self.app:
            self.setup(self.app, prefix=self.prefix)
        self.authorize: t.Callable[[muffin.Request], t.Awaitable] = to_awaitable(lambda r: True)

    @property
    def logger(self):
        if self.app is None:
            raise RuntimeError('API must be binded to an app.')

        return self.app.logger

    def setup(self, app: muffin.Application, prefix: str = ''):
        """Initialize the API."""
        self.app = app
        self.prefix = prefix.rstrip('/')

        # Setup routing
        self.router.trim_last_slash = self.app.router.trim_last_slash
        self.router.validate_cb = self.app.router.validate_cb               # type: ignore
        self.router.MethodNotAllowed = self.app.router.MethodNotAllowed     # type: ignore
        self.router.NotFound = self.app.router.NotFound                     # type: ignore
        self.app.router.route(self.prefix)(self.router)

    def route(self, path: t.Union[str, t.Any], *paths: str, **params):
        """Route an endpoint by the API."""
        from .endpoint import Endpoint

        def wrapper(cb):
            cb = self.router.route(*paths, **params)(cb)
            cb._api = self
            return cb

        if isinstance(path, str):
            paths = (path, *paths)

        # Generate URL paths automatically
        elif issubclass(path, Endpoint):
            endpoint = path
            paths = (f'/{ endpoint.meta.name }',
                     f'/{ endpoint.meta.name }/{{{ endpoint.meta.name }}}')
            return wrapper(endpoint)

        else:
            raise Exception("Invalid endpoint")  # TODO

        return wrapper

    def authorization(self, auth: AUTH) -> AUTH:
        """Bind an authorization flow to self API."""
        self.authorize = auth
        return auth
