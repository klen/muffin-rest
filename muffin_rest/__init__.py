"""REST helpers for Muffin Framework."""
# Package information
# ===================

__version__ = "1.4.1"
__project__ = "muffin-rest"
__author__ = "Kirill Klenov <horneds@gmail.com>"
__license__ = "MIT"


# Import Muffin-REST Elements to the root module namespace
from .api import *          # noqa
from .filters import *      # noqa
from .handlers import *     # noqa
from .exceptions import *   # noqa

try:
    from .peewee import PWRESTHandler, PWFilter # noqa
except ImportError:
    pass
