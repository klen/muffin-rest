from enum import Enum

import marshmallow as ma
import pytest

from muffin_rest.schemas import EnumField


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
