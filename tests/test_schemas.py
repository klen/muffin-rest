from enum import Enum

import marshmallow as ma
import pytest

from muffin_rest.handler import RESTBase
from muffin_rest.marshmallow import load_data
from muffin_rest.schemas import EnumField


def test_schema_meta_additional_rejected():
    with pytest.raises(ValueError, match="schema_fields"):

        class Pet(RESTBase):
            class Meta:
                name = "pet"
                schema_meta = {"additional": ("extra",)}


def test_enum_field():
    class Color(Enum):
        RED = "red"
        GREEN = "green"
        BLUE = "blue"

    field = EnumField(enum=Color)
    assert field.deserialize("red") == Color.RED
    assert field.deserialize("blue") == Color.BLUE
    assert field.deserialize("green") == Color.GREEN

    with pytest.raises(ma.ValidationError, match="Must be one of"):
        field.deserialize("yellow")


def test_enum_field_by_name():
    class Color(Enum):
        RED = 1
        GREEN = 2
        BLUE = 3

    field = EnumField(enum=Color, by_value=False)
    assert field.deserialize("RED") == Color.RED
    assert field.deserialize("BLUE") == Color.BLUE
    assert field.deserialize("GREEN") == Color.GREEN

    with pytest.raises(ma.ValidationError, match="Must be one of"):
        field.deserialize("YELLOW")


def test_enum_field_serialize():
    class Color(Enum):
        RED = "red"

    field = EnumField(enum=Color)
    assert field.serialize("color", {"color": Color.RED}) == "red"
    assert field.serialize("color", {"color": None}) is None

    by_name = EnumField(enum=Color, by_value=False)
    assert by_name.serialize("color", {"color": Color.RED}) == "RED"

    with pytest.raises(ma.ValidationError, match="value is invalid"):
        field.serialize("color", {"color": "unknown"})


async def test_load_data_without_schema():
    assert await load_data({"a": 1}) == {"a": 1}
