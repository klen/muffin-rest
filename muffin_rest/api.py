"""!!! STILL NOT IMPLEMENTED. WORK IN PROGRESS !!!."""
import asyncio
import re
from types import FunctionType

import muffin
from aiohttp import web


PREFIX_RE = re.compile('(/|\s)')


class ApiRoute(web.Route):

    """Support multiple routers."""

    def __init__(self, api):
        """Initialize the route."""
        self.api = api
        self.router = web.UrlDispatcher()
        super(ApiRoute, self).__init__('*', None, api.prefix_name)

    def match(self, path):
        """Check path for API."""
        if path.startswith(self.api.prefix):
            path = path[len(self.api.prefix):]
            for name, route in self.router.items():
                match_info = route.match(path)
                if match_info is not None:
                    match_info['api-name'] = name
                    return match_info
        return None

    @asyncio.coroutine
    def handler(self, request):
        """Handle request."""
        route = self.router[request.match_info['api-name']]
        response = yield from route._handler(request)
        return response

    def url(self, **kwargs):
        """Do nothing for now."""
        return self.api.prefix


class Api():

    """Bind group of resources together."""

    def __init__(self, app, prefix='/api', scheme=False):
        """Initialize the API."""
        self.app = app
        self.prefix = prefix.rstrip('/')
        self.prefix_name = PREFIX_RE.sub('.', prefix.strip('/'))
        self.handlers = {}
        self.urls = ApiRoute(self)
        self.app.router.register_route(self.urls)
        if scheme:
            path = '/'.join((self.prefix, scheme.strip('/')))
            handler = muffin.Handler.from_view(self.render_scheme, 'GET')
            app.register(path)(handler)

    def register(self, *paths, methods=None, name=None):
        """Register handler to the API."""
        if isinstance(methods, str):
            methods = [methods]

        def wrapper(handler):

            if isinstance(handler, FunctionType):
                handler = muffin.Handler.from_view(handler, *(methods or ['GET']))

            if handler.name in self.handlers:
                raise muffin.MuffinException('Handler is already registered: %s' % handler.name)

            self.handlers[handler.name] = handler

            handler.connect(
                self.app, *paths, methods=methods,
                name=name or "%s.%s" % (self.prefix_name, handler.name), router=self.urls.router)

            return handler

        # Support for @app.register(func)
        if len(paths) == 1 and callable(paths[0]):
            view = paths[0]
            paths = []
            return wrapper(view)

        return wrapper

    def render_scheme(self, request):
        """Render API Scheme."""
        response = {}

        for name, handler in self.handlers.items():
            scheme = {'methods': handler.methods, 'desc': handler.__doc__}
            scheme.update(getattr(handler, 'scheme', lambda: {})())
            response[name] = scheme

        return response

#  pylama:ignore=W1401,W0212
