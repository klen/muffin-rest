import marshmallow as ma
import pytest

from muffin_rest.filters import Filter


@pytest.fixture
def flt():
    return Filter("test")


def test_parse(flt):
    ops = flt.parse({"test": "value"})
    assert tuple(ops) == ((flt.operators["=="], "value"),)

    ops = flt.parse({"test": {"$ne": "value"}})
    assert tuple(ops) == ((flt.operators["$ne"], "value"),)


def test_parse_array(flt):
    flt.schema_field = ma.fields.Integer()
    ops = flt.parse({"test": {"$in": [1, "2", 3]}})
    assert tuple(ops) == ((flt.operators["$in"], [1, 2, 3]),)


def test_parse_multi(flt):
    ops = flt.parse({"test": {"$ne": "value", "$gt": "value2"}})
    assert tuple(ops) == (
        (flt.operators["$ne"], "value"),
        (flt.operators["$gt"], "value2"),
    )


def test_parse_or():
    flt = Filter("test")
    ops = flt.parse({"test": {"$or": ["value", "value2"]}})
    assert tuple(ops) == (
        (
            flt.operators["$or"],
            [
                (flt.operators["=="], "value"),
                (flt.operators["=="], "value2"),
            ],
        ),
    )


def test_parse_or2():
    flt = Filter("test")
    ops = flt.parse({"test": {"$or": [{"$in": [1, 2]}, {"$in": [3, 4]}]}})
    assert tuple(ops) == (
        (
            flt.operators["$or"],
            [
                (flt.operators["$in"], [1, 2]),
                (flt.operators["$in"], [3, 4]),
            ],
        ),
    )


async def test_apply_list_ops(flt):
    collection = [{"test": "a"}, {"test": "b"}, {"test": "c"}]

    _, out = await flt.apply(collection, data={"test": {"$in": ["a", "c"]}})
    assert out == [{"test": "a"}, {"test": "c"}]

    _, out = await flt.apply(collection, data={"test": {"$or": ["a", "c"]}})
    assert out == [{"test": "a"}, {"test": "c"}]

    _, out = await flt.apply(collection, data={"test": {"$and": [{"$eq": "a"}]}})
    assert out == [{"test": "a"}]

    _, out = await flt.apply(collection, data={"test": {"$not": [{"$eq": "a"}]}})
    assert out == [{"test": "b"}, {"test": "c"}]

    _, out = await flt.apply(collection, data={"test": {"$nor": [{"$eq": "a"}, {"$eq": "c"}]}})
    assert out == [{"test": "b"}]
