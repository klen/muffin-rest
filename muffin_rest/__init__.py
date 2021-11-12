"""REST helpers for Muffin Framework."""

__version__ = "4.0.1"
__project__ = "muffin-rest"
__author__ = "Kirill Klenov <horneds@gmail.com>"
__license__ = "MIT"

# Default query params
LIMIT_PARAM = 'limit'
OFFSET_PARAM = 'offset'


from .api import API                # noqa
from .handler import RESTHandler    # noqa
from .errors import APIError        # noqa


# Just an alias to support legacy style
Api = API


__all__ = (
    'API', 'Api', 'RESTHandler', 'APIError',
    'PWRESTHandler', 'PWFilter', 'PWFilters', 'PWSort', 'PWSorting',
    'SARESTHandler', 'SAFilter', 'SAFilters', 'SASort', 'SASorting',
    'MongoRESTHandler', 'MongoFilter', 'MongoFilters', 'MongoSort', 'MongoSorting',
)


# Support Peewee ORM
try:
    from .peewee import PWRESTHandler
    from .peewee.filters import PWFilter, PWFilters
    from .peewee.sorting import PWSort, PWSorting
except ImportError as exc:
    pass


# Support SQLAlchemy ORM
try:
    from .sqlalchemy import SARESTHandler
    from .sqlalchemy.filters import SAFilter, SAFilters
    from .sqlalchemy.sorting import SASort, SASorting
except ImportError:
    pass


# Support Mongo ORM
try:
    from .mongo import MongoRESTHandler
    from .mongo.filters import MongoFilter, MongoFilters
    from .mongo.sorting import MongoSort, MongoSorting
except ImportError:
    pass

# pylama:ignore=W0611
