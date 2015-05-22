""" .

!!! STILL NOT IMPLEMENTED. WORK IN PROGRESS !!!

"""

import re
from aiohttp import web


PREFIX_RE = re.compile('(/|\s)')


class ApiRoute(web.DynamicRoute):

    """ . """

    pass


class Api():

    """ Support API. """

    def __init__(self, app, prefix='/api'):
        """ Initialize the API. """
        self.app = app
        self.prefix = prefix.strip('/')
        self.prefix_name = PREFIX_RE.sub('-', self.prefix)
        self.handlers = {}

    def register(self, handler, *paths, **kwargs):
        """ Register handler to application. """
        self.handlers[handler.name] = handler
        self.app.register(*paths, **kwargs)(handler)
