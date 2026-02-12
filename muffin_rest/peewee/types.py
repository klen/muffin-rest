from typing import TypeVar

from peewee import Model, ModelSelect

TVModel = TypeVar("TVModel", bound=Model)
TVCollection = TypeVar("TVCollection", bound=ModelSelect)
