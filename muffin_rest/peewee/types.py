import sys

from peewee import Model, ModelSelect

if sys.version_info < (3, 13):
    from typing_extensions import TypeVar  # py311,py312
else:
    from typing import TypeVar

TVResource = TypeVar("TVResource", bound=Model, default=Model)
TVCollection = TypeVar("TVCollection", bound=ModelSelect, default=ModelSelect)
