import ujson

from muffin import HTTPNotFound, HTTPBadRequest, HTTPForbidden


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
