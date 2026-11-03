import marshmallow as ma
import pytest

from muffin_rest.errors import APIError
from muffin_rest.handler import RESTHandler
from muffin_rest.limits import MemoryRateLimiter


class FakeSchema(ma.Schema):
    def dump(self, data, **_):
        return data

    def load(self, data, **_):
        return data


@pytest.fixture
def api(app):
    from muffin_rest import API

    api = API(app, prefix="/api", title="API Title")

    @api.authorization
    async def fake_auth(request):
        return not request.url.query.get("guest")

    return api


async def test_conf(client):
    res = await client.get("/")
    assert res.status_code == 200
    assert await res.text() == "OK"


async def test_api(app, client):
    from muffin_rest import API

    api = API()
    assert api

    api.setup(app, prefix="/api")
    assert api.app
    assert api.prefix == "/api"

    res = await client.get("/api")
    assert res.status_code == 404


async def test_api_methods(api, client):
    @api.route("/simple")
    async def simple_endpoint(_):
        return {"data": "simple"}

    res = await client.get("/api/simple")
    assert res.status_code == 200
    assert await res.json() == {"data": "simple"}


def test_api_not_initialized():
    from muffin_rest import API

    api = API()
    assert repr(api) == "<API >"

    with pytest.raises(RuntimeError, match="not initialized"):
        _ = api.logger


def test_api_error_with_dict_content():
    err = APIError({"error": False}, status_code=418, extra="x")

    assert err.status_code == 418
    assert err.content == b'{"error": false, "extra": "x"}'


def test_handler_not_binded():
    from muffin_rest.errors import HandlerNotBindedError

    class Simple(RESTHandler):
        async def prepare_collection(self, request):
            return []

    handler = object.__new__(Simple)
    with pytest.raises(HandlerNotBindedError):
        _ = handler.api


async def test_handler(api, client):
    from muffin_rest import RESTHandler
    from muffin_rest.filters import Filters
    from muffin_rest.sorting import Sorting

    assert RESTHandler is not None

    @api.route("/simple")
    class Simple(RESTHandler):
        methods = "get", "put"

        class Meta(RESTHandler.Meta):
            name = "simple"
            sorting = ("test",)
            schema_base = FakeSchema

        async def prepare_collection(self, request):
            return f"SIMPLE {request.method}"

    assert Simple.meta
    assert Simple.meta.name == "simple"
    assert Simple.meta.limit == 0
    assert Simple.meta.filters is not None
    assert isinstance(Simple.meta.filters, Filters)
    assert Simple.meta.sorting is not None
    assert isinstance(Simple.meta.sorting, Sorting)
    assert Simple.methods == {"GET", "PUT"}
    assert api.router.routes()[2].methods == Simple.methods
    assert Simple.meta.Schema
    assert issubclass(Simple.meta.Schema, FakeSchema)
    assert Simple.meta.Schema.opts
    assert Simple.meta.Schema.opts.unknown == "exclude"

    res = await client.get("/api/simple")
    assert res.status_code == 200
    body = await res.body()
    assert body == b'"SIMPLE GET"'

    res = await client.put("/api/simple")
    assert res.status_code == 404
    assert await res.json() == {
        "error": True,
        "message": "Nothing matches the given URI",
    }

    res = await client.post("/api/simple")
    assert res.status_code == 405

    res = await client.get("/api/simple?guest=1")
    assert res.status_code == 401
    assert await res.json() == {
        "error": True,
        "message": "No permission -- see authorization schemes",
    }


@pytest.fixture
def source():
    return [1, 2, 3]


@pytest.fixture
def source_endpoint(api, source):  # noqa: C901
    from muffin_rest import APIError, RESTHandler

    @api.route
    class Source(RESTHandler):
        class Meta:
            name = "source"
            filters = ("val",)
            limit = 10
            Schema = FakeSchema

        async def prepare_collection(self, _):
            return source

        async def prepare_resource(self, request):
            key = request["path_params"].get("id")
            if not key:
                return

            try:
                return source[int(key)]
            except (IndexError, ValueError) as exc:
                raise APIError.NOT_FOUND("Resource not found") from exc

        async def paginate(self, request, limit, offset):
            return self.collection[offset : offset + limit], len(source)

        async def load(self, request, resource=None):
            data = await super().load(request, resource=resource)
            if resource:
                idx = source.index(resource)
                source[idx] = data
            return data

        async def save(self, request, resource=None, *, update=False):
            if resource not in source:
                source.append(resource)
            return resource

        async def remove(self, request, resource=None):
            source.remove(resource)

        @RESTHandler.route("/source/custom", methods="get")
        async def custom(self, request, resource=None):
            return "source: custom"

    assert Source.meta.filters
    assert Source.meta.filters.mutations
    return Source


async def test_source_collection(apiclient, source_endpoint):
    res = await apiclient.get("/api/source")
    assert res.status_code == 200
    assert await res.json() == [1, 2, 3]


async def test_source_resource(apiclient, source_endpoint):
    res = await apiclient.get("/api/source/1")
    assert res.status_code == 200
    assert await res.json() == 2


async def test_source_resource_not_found(apiclient, source_endpoint):
    res = await apiclient.get("/api/source/99")
    assert res.status_code == 404
    assert await res.json() == {"error": True, "message": "Resource not found"}


async def test_source_create(apiclient, source_endpoint, source):
    res = await apiclient.post("/api/source", json=42)
    assert res.status_code == 200
    assert await res.json() == 42
    assert source == [1, 2, 3, 42]


async def test_source_update(apiclient, source_endpoint, source):
    res = await apiclient.put("/api/source/2", json=99)
    assert res.status_code == 200
    assert await res.json() == 99
    assert source == [1, 2, 99]


async def test_source_delete(apiclient, source_endpoint, source):
    res = await apiclient.delete("/api/source/2")
    assert res.status_code == 200
    assert source == [1, 2]


async def test_source_filter(apiclient, source_endpoint):
    res = await apiclient.get("/api/source", filters={"val": 2})
    assert res.status_code == 200
    assert await res.json() == [2]

    res = await apiclient.get("/api/source", filters={"val": {">=": 2}})
    assert res.status_code == 200
    assert await res.json() == [2, 3]


async def test_source_paginate(apiclient, source, source_endpoint):
    res = await apiclient.get("/api/source", limit=2)
    assert res.status_code == 200
    assert res.headers["x-total"] == str(len(source))
    assert res.headers["x-limit"] == "2"
    assert res.headers["x-offset"] == "0"
    assert await res.json() == [1, 2]

    res = await apiclient.get("/api/source", limit=2, offset=1)
    assert res.status_code == 200
    assert await res.json() == [2, 3]


async def test_source_custom_route(apiclient, source_endpoint):
    res = await apiclient.get("/api/source/custom")
    assert res.status_code == 200
    assert await res.text() == "source: custom"

    # Unknown ids fall through to the detail route, which returns 404
    res = await apiclient.post("/api/source/custom")
    assert res.status_code == 404


async def test_pagination_clamps(api, apiclient):
    from muffin_rest import RESTHandler

    source = list(range(100))

    @api.route
    class Source(RESTHandler):
        class Meta:
            name = "source"
            limit = 10
            Schema = FakeSchema

        async def prepare_collection(self, request):
            return source

        async def paginate(self, request, *, limit=0, offset=0):
            return source[offset : offset + limit], len(source)

    # limit=0 clamps up to limit_min (default 1)
    res = await apiclient.get("/api/source", limit=0)
    assert res.status_code == 200
    assert await res.json() == [0]

    # negative offset clamps to 0
    res = await apiclient.get("/api/source", offset=-5)
    assert res.status_code == 200
    assert await res.json() == list(range(10))

    # non numeric params are rejected
    res = await apiclient.get("/api/source?limit=abc")
    assert res.status_code == 400
    assert await res.json() == {"error": True, "message": "Pagination params are invalid"}


async def test_pagination_limit_min_zero(api, apiclient):
    from muffin_rest import RESTHandler

    source = list(range(100))

    @api.route
    class AllSource(RESTHandler):
        class Meta:
            name = "allsource"
            limit = 10
            limit_min = 0
            Schema = FakeSchema

        async def prepare_collection(self, request):
            return source

        async def paginate(self, request, *, limit=0, offset=0):
            return source[offset : offset + limit], len(source)

    # limit_min=0 allows limit=0 to return everything
    res = await apiclient.get("/api/allsource", limit=0)
    assert res.status_code == 200
    json = await res.json()
    assert json == source


async def test_bad_request(api, client):
    from muffin_rest import RESTHandler

    @api.route("/simple")
    class Simple(RESTHandler):
        methods = "get", "post"

        class Meta:
            name = "simple"

        async def prepare_collection(self, request):
            return f"SIMPLE {request.method}"

        async def save(self, request, resource=None, *, update=False):
            pass

    res = await client.post(
        "/api/simple", data="invalid", headers={"content-type": "application/json"}
    )
    assert res.status_code == 400


async def test_handlers_with_schema(api, client):
    from muffin_rest import RESTHandler

    pets = []

    @api.route("/pets", "/pets/{pet}")
    class Pet(RESTHandler):
        methods = "get", "post"

        class Meta:
            name = "pet"

            class Schema(ma.Schema):
                name = ma.fields.String(required=True)

        async def prepare_collection(self, request):
            return pets

        async def save(self, request, resource, *, update=False):
            pets.append(resource)
            return resource

    res = await client.post("/api/pets", json={})
    assert res.status_code == 400
    json = await res.json()
    assert json
    assert json["errors"]

    res = await client.post("/api/pets", json={"name": "muffin"})
    assert res.status_code == 200
    json = await res.json()
    assert json == {"name": "muffin"}

    res = await client.get("/api/pets")
    assert res.status_code == 200
    json = await res.json()
    assert json == [{"name": "muffin"}]


async def test_schema_only_exclude(api, client):
    from muffin_rest import RESTHandler

    @api.route
    class Pet(RESTHandler):
        class Meta:
            name = "pet"

            class Schema(ma.Schema):
                name = ma.fields.String()
                age = ma.fields.Integer()

        async def prepare_collection(self, request):
            return [{"name": "muffin", "age": 3}]

    res = await client.get("/api/pet?schema_only=name")
    assert res.status_code == 200
    json = await res.json()
    assert json == [{"name": "muffin"}]

    res = await client.get("/api/pet?schema_exclude=age")
    assert res.status_code == 200
    json = await res.json()
    assert json == [{"name": "muffin"}]


async def test_handler_with_path(api, client):
    from muffin_rest import RESTHandler

    @api.route
    class Simple(RESTHandler):
        methods = "get", "patch"

        class Meta:  # type: ignore[]
            name = "simple"

        async def prepare_collection(self, request):
            return [1, 2, 3, 4]

        async def patch(self, request, **kwargs):
            return True

    res = await client.get("/api/simple")
    assert res.status_code == 200

    res = await client.patch("/api/simple")
    assert res.status_code == 200


async def test_handler_default_methods(api, client):
    from muffin_rest import RESTHandler

    @api.route
    class Simple(RESTHandler):
        class Meta:
            name = "simple"

        async def prepare_collection(self, request):
            return [1]

    res = await client.get("/api/simple")
    assert res.status_code == 200

    for method in ("patch", "head", "options"):
        res = await getattr(client, method)("/api/simple")
        assert res.status_code == 405


async def test_rate_limit(api, client, aiolib):

    rate_limiter = MemoryRateLimiter(10)

    @api.route
    class Simple(RESTHandler):
        methods = "get"

        async def authorize(self, request):
            if not await rate_limiter.check(request.client[0]):
                raise APIError.TOO_MANY_REQUESTS("Rate limit exceeded")

            return aiolib[0]

        async def prepare_collection(self, request):
            return [1, 2, 3, 4]

    for _ in range(10):
        res = await client.get("/api/simple")
        assert res.status_code == 200

    res = await client.get("/api/simple")
    assert res.status_code == 429
