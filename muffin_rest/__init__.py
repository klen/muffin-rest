"""REST helpers for Muffin Framework."""

from contextlib import suppress

__version__ = "4.2.7"
__project__ = "muffin-rest"
__author__ = "Kirill Klenov <horneds@gmail.com>"
__license__ = "MIT"

# Default query params
LIMIT_PARAM = "limit"
OFFSET_PARAM = "offset"


from .api import API  # noqa
from .errors import APIError  # noqa
from .handler import RESTHandler  # noqa

# Just an alias to support legacy style
Api = API


__all__ = (
    "API",
    "Api",
    "RESTHandler",
    "APIError",
    "PWRESTHandler",
    "PWFilter",
    "PWFilters",
    "PWSort",
    "PWSorting",
    "SARESTHandler",
    "SAFilter",
    "SAFilters",
    "SASort",
    "SASorting",
    "MongoRESTHandler",
    "MongoFilter",
    "MongoFilters",
    "MongoSort",
    "MongoSorting",
)

# Support Peewee ORM
with suppress(ImportError):
    from .peewee import PWRESTHandler
    from .peewee.filters import PWFilter, PWFilters
    from .peewee.sorting import PWSort, PWSorting


# Support SQLAlchemy ORM
with suppress(ImportError):
    from .sqlalchemy import SARESTHandler
    from .sqlalchemy.filters import SAFilter, SAFilters
    from .sqlalchemy.sorting import SASort, SASorting


# Support Mongo ORM
with suppress(ImportError):
    from .mongo import MongoRESTHandler
    from .mongo.filters import MongoFilter, MongoFilters
    from .mongo.sorting import MongoSort, MongoSorting

# pylama:ignore=W0611
