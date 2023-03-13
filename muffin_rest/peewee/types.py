from typing import TypeVar

from peewee import Model, Query

TVModel = TypeVar("TVModel", bound=Model)
TVCollection = TypeVar("TVCollection", bound=Query)
