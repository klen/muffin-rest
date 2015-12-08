"""REST helpers for Muffin Framework."""
import ujson
from muffin import HTTPNotFound, HTTPBadRequest, HTTPForbidden


# Package information
# ===================

__version__ = "0.3.1"
__project__ = "muffin-rest"
__author__ = "Kirill Klenov <horneds@gmail.com>"
__license__ = "MIT"


class JSONResponse:

    """Accept JSON data.

    Helper which makes JSON responses more easy.

    ::

        return JSONResponse(json={'json': 'here'})

    """

    def __init__(self, *, json=None, **kwargs):
        """Convert JSON data to text."""
        if json:
            kwargs.setdefault('text', ujson.dumps(json))
            kwargs.setdefault('content_type', 'application/json')
        super(JSONResponse, self).__init__(**kwargs)


class RESTNotFound(JSONResponse, HTTPNotFound):

    """Resource is not found."""

    pass


class RESTBadRequest(JSONResponse, HTTPBadRequest):

    """Request data is bad."""

    pass


class RESTForbidden(JSONResponse, HTTPForbidden):

    """Access to resource is forbidden."""

    pass

# Import Muffin-REST Elements to the root module namespace
from .api import *      # noqa
from .filters import *  # noqa
from .forms import *    # noqa
from .handlers import * # noqa

try:
    from .peewee import PWRESTHandler           # noqa
    from .peewee import PWFilter, PWLikeFilter  # noqa
except ImportError:
    pass
