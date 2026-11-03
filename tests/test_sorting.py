"""Unit tests for the generic sorting layer."""

from types import SimpleNamespace

from muffin_rest.sorting import Sort, Sorting, to_sort


class FakeRequest:
    """Request with query params only."""

    def __init__(self, query):
        self.url = SimpleNamespace(query=query)


class FakeHandler:
    """Sorting does not touch the handler."""


class CaptureSort(Sort):
    """Record calls instead of sorting."""

    def __init__(self, name, applied):
        super().__init__(name)
        self.applied = applied

    async def apply(self, collection, *, desc=False, **ctx):
        self.applied.append((self.name, desc, ctx))
        return collection


def build_sorting(*names):
    applied = []
    sorting = Sorting(FakeHandler, names)
    sorting.mutations = {name: CaptureSort(name, applied) for name in sorting.mutations}
    return sorting, applied


def test_to_sort_skips_empty_entries():
    assert list(to_sort(["a", "-b", "", "-"])) == [("a", False), ("b", True)]


async def test_sort_sorts_by_attribute():
    items = [SimpleNamespace(name=name) for name in ("b", "c", "a")]

    assert [item.name for item in await Sort("name").apply(items)] == ["a", "b", "c"]
    assert [item.name for item in await Sort("name").apply(items, desc=True)] == [
        "c",
        "b",
        "a",
    ]


async def test_sorting_applies_request_order():
    sorting, applied = build_sorting("a", "b")

    await sorting.apply(FakeRequest({"sort": "b,-a"}), [])

    assert [(name, desc) for name, desc, _ in applied] == [("b", False), ("a", True)]


async def test_sorting_ignores_unknown_names():
    sorting, applied = build_sorting("a")

    _, params = await sorting.apply(FakeRequest({"sort": "missing,a"}), [])

    assert [(name, desc) for name, desc, _ in applied] == [("a", False)]
    assert params == {"a": False}


async def test_sorting_forwards_context():
    sorting, applied = build_sorting("a", "b")
    ctx = {"db_session": "test", "user_id": 42}

    await sorting.apply(FakeRequest({"sort": "a,-b"}), [], **ctx)

    assert [received for _, _, received in applied] == [ctx, ctx]


async def test_sorting_falls_back_to_default():
    sorting = Sorting(FakeHandler, (("name", {"default": True}),))

    collection, params = await sorting.apply(FakeRequest({}), [3, 1, 2])

    assert collection == [1, 2, 3]
    assert params == {}
