""" REST helpers for Muffin Framework. """

# Package information
# ===================

__version__ = "0.0.13"
__project__ = "muffin-rest"
__author__ = "Kirill Klenov <horneds@gmail.com>"
__license__ = "MIT"

from .api import *      # noqa
from .forms import *    # noqa
from .handlers import * # noqa

try:
    from .peewee import PWRESTHandler # noqa
except ImportError:
    pass
