""" REST helpers for Muffin Framework. """

from muffin import HTTPNotFound, HTTPBadRequest, HTTPForbidden

# Package information
# ===================

__version__ = "0.0.15"
__project__ = "muffin-rest"
__author__ = "Kirill Klenov <horneds@gmail.com>"
__license__ = "MIT"


class RESTNotFound(HTTPNotFound):

    """ Custom excption class for stopping default application error handlers. """

    pass


class RESTBadRequest(HTTPBadRequest):

    """ Custom excption class for stopping default application error handlers. """

    pass


class RESTForbidden(HTTPForbidden):

    """ Custom excption class for stopping default application error handlers. """

    pass

from .api import *      # noqa
from .forms import *    # noqa
from .handlers import * # noqa

try:
    from .peewee import PWRESTHandler # noqa
except ImportError:
    pass
