from types import SimpleNamespace

import marshmallow as ma
import pytest

from muffin_rest.filters import Filter, Filters, MultiFilter


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


async def test_multi_filter():
    class OrFilter(MultiFilter):
        async def filter(self, collection, ops, **ctx):  # type: ignore[bad-override]
            conditions = [self.filters[name].condition(*flt_ops) for name, flt_ops in ops.items()]
            return [item for item in collection if any(cond(item) for cond in conditions)]

    handler = SimpleNamespace(meta=SimpleNamespace(Schema=SimpleNamespace(_declared_fields={})))
    filters = Filters(handler, (OrFilter("q", filters=("a", "b")),))
    multi = filters.mutations["q"]
    assert set(multi.filters) == {"a", "b"}

    collection = [{"a": 1, "b": 3}, {"a": 2, "b": 2}, {"a": 3, "b": 1}]
    ops, out = await multi.apply(collection, data={"q": {"a": 1, "b": 1}})
    assert out == [collection[0], collection[2]]
    assert set(ops) == {"a", "b"}

    # Default AND, and a filter is skipped when none of its names are present
    multi = filters.convert(MultiFilter("q", filters=("a", "b")))
    _, out = await multi.apply(collection, data={"q": {"a": 2, "b": 2}})
    assert out == [collection[1]]

    ops, out = await multi.apply(collection, data={"q": {"a": 2}})
    assert set(ops) == {"a"}
    assert out == [collection[1]]

    # `filters` accepts the same entries as `Meta.filters`
    multi = filters.convert(MultiFilter("q", filters=(("b", {"operator": "$ne"}), Filter("a"))))
    assert set(multi.filters) == {"a", "b"}
    assert multi.filters["b"].default_operator == "$ne"
