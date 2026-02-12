from peewee import Model, ModelSelect
from typing_extensions import TypeVar  # py310,py311,py312

TVResource = TypeVar("TVResource", bound=Model, default=Model)
TVCollection = TypeVar("TVCollection", bound=ModelSelect, default=ModelSelect)
