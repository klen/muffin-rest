""" .

!!! STILL NOT IMPLEMENTED. WORK IN PROGRESS !!!

"""

import re
import muffin
import asyncio
from types import FunctionType
from aiohttp import web


PREFIX_RE = re.compile('(/|\s)')


class ApiRoute(web.Route):

    """ Support multiplie routers. """

    def __init__(self, api):
        """ Init router. """
        self.api = api
        self._name = api.prefix_name
        self._path = api.prefix
        self._method = "*"
        self.router = web.UrlDispatcher()

    def match(self, path):
        """ Check path for API. """
        if path.startswith(self.api.prefix):
            path = path[len(self.api.prefix):]
            for name, route in self.router.items():
                match_info = route.match(path)
                if match_info is not None:
                    match_info['api-name'] = name
                    return match_info
        return None

    @asyncio.coroutine
    def _handler(self, request):
        route = self.router[request.match_info['api-name']]
        response = yield from route._handler(request)
        return response

    def url(self, **kwargs):
        """ Do nothing for now. """
        pass


class Api():

    """ Support API. """

    def __init__(self, app, prefix='/api', scheme=False):
        """ Initialize the API. """
        self.app = app
        self.prefix = prefix.rstrip('/')
        self.prefix_name = PREFIX_RE.sub('-', prefix.strip('/'))
        self.handlers = {}
        self.urls = ApiRoute(self)
        self.app.router.register_route(self.urls)
        if scheme:
            path = '/'.join((self.prefix, scheme.strip('/')))
            handler = muffin.Handler.from_view(self.render_scheme, 'GET')
            app.register(path)(handler)

    def register(self, *paths, methods=None, name=None):
        """ Register handler to application. """
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
                name=name or "%s-%s" % (self.prefix_name, handler.name), router=self.urls.router)

            return handler

        # Support for @app.register(func)
        if len(paths) == 1 and callable(paths[0]):
            view = paths[0]
            paths = []
            return wrapper(view)

        return wrapper

    def render_scheme(self, request):
        """ Render API Scheme. """
        response = {}

        for name, handler in self.handlers.items():
            scheme = {'methods': handler.methods, 'desc': handler.__doc__}
            scheme.update(getattr(handler, 'scheme', lambda: {})())
            response[name] = scheme

        return response
