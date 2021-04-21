"""REST helpers for Muffin Framework."""

__version__ = "2.6.4"
__project__ = "muffin-rest"
__author__ = "Kirill Klenov <horneds@gmail.com>"
__license__ = "MIT"

# Default query params
FILTERS_PARAM = 'where'
LIMIT_PARAM = 'limit'
OFFSET_PARAM = 'offset'
SORT_PARAM = 'sort'


from .api import API                # noqa
from .handler import RESTHandler    # noqa
from .errors import APIError        # noqa

# Just an alias to support legacy style
Api = API


try:
    from .peewee import PWRESTHandler, PWFilter
except ImportError:
    pass


try:
    from .sqlalchemy import SARESTHandler, SAFilter
except ImportError:
    pass


try:
    from .mongo import MongoRESTHandler, MongoFilter
except ImportError:
    pass
