""" REST helpers for Muffin Framework. """

from muffin import HTTPNotFound, HTTPBadRequest, HTTPForbidden
import ujson

# Package information
# ===================

__version__ = "0.1.0"
__project__ = "muffin-rest"
__author__ = "Kirill Klenov <horneds@gmail.com>"
__license__ = "MIT"


class JSONResponse:

    """ Accept JSON data. """

    def __init__(self, *, json=None, **kwargs):
        """ Convert JSON data to text. """
        if json:
            kwargs.setdefault('text', ujson.dumps(json))
            kwargs.setdefault('content_type', 'application/json')
        super(JSONResponse, self).__init__(**kwargs)


class RESTNotFound(JSONResponse, HTTPNotFound):

    """ Custom excption class for stopping default application error handlers. """

    pass


class RESTBadRequest(JSONResponse, HTTPBadRequest):

    """ Custom excption class for stopping default application error handlers. """

    pass


class RESTForbidden(JSONResponse, HTTPForbidden):

    """ Custom exception class for stopping default application error handlers. """

    pass

from .api import *      # noqa
from .filters import *  # noqa
from .forms import *    # noqa
from .handlers import * # noqa

try:
    from .peewee import PWRESTHandler           # noqa
    from .peewee import PWFilter, PWLikeFilter  # noqa
except ImportError:
    pass
