from typing import TypeVar

from peewee import Query

TVCollection = TypeVar("TVCollection", bound=Query)
