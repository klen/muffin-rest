"""REST helpers for Muffin Framework."""

from contextlib import suppress

# Default query params
LIMIT_PARAM = "limit"
OFFSET_PARAM = "offset"


from .api import API
from .errors import APIError
from .handler import RESTHandler

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

# ruff: noqa: E402
