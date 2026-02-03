import pytest
import sqlalchemy as sa
from muffin_databases import Plugin as DB


@pytest.fixture(scope="module")
def aiolib():
    return "asyncio", {"loop_factory": None}


@pytest.fixture
async def db(app):
    db = DB(app, url="sqlite:///:memory:", params={"force_rollback": True})
    async with db, db.connection():
        yield db


@pytest.fixture
async def Resource(db):
    meta = sa.MetaData()
    Category = sa.Table(
        "category",
        meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
    )
    Resource = sa.Table(
        "resource",
        meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("active", sa.Boolean, server_default="0", nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("created", sa.DateTime, server_default=sa.func.datetime(), nullable=False),
        sa.Column("count", sa.Integer),
        sa.Column(
            "category_id",
            sa.ForeignKey("category.id"),
            nullable=False,
            server_default="1",
        ),
    )

    await db.execute(sa.schema.CreateTable(Category))
    await db.execute(Category.insert(), values={"name": "test"})

    await db.execute(sa.schema.CreateTable(Resource))
    return Resource


@pytest.fixture
async def resource(Resource, db):
    return await db.execute(Resource.insert(), values={"name": "test"})


@pytest.fixture
def ResourceEndpoint(api, db, Resource):
    from muffin_rest.sqlalchemy import SARESTHandler
    from muffin_rest.sqlalchemy.filters import SAFilter

    @api.route
    class ResourceEndpoint(SARESTHandler):
        class Meta:
            database = db
            filters = (
                "active",
                SAFilter("name"),
                ("oid", {"field": "id"}),
                SAFilter("category", field=Resource.c.category_id),
            )
            limit = 10
            sorting = ("name", {"default": "asc"}), "count"
            table = Resource

        @SARESTHandler.route("/resource/action")
        async def action(self, request, resource=None):
            rows = await self.meta.database.fetch_all(self.collection)
            return await self.dump(request, rows, many=True)

    return ResourceEndpoint


def test_imports():
    from muffin_rest import SAFilter, SAFilters, SARESTHandler, SASort, SASorting

    assert SARESTHandler is not None
    assert SAFilter is not None
    assert SAFilters is not None
    assert SASort is not None
    assert SASorting is not None


def test_base(ResourceEndpoint, api):
    assert ResourceEndpoint
    assert ResourceEndpoint.meta.name == "resource"
    assert ResourceEndpoint.meta.Schema
    assert ResourceEndpoint.meta.Schema.opts.dump_only == ("id",)
    assert ResourceEndpoint.meta.sorting
    assert ResourceEndpoint.meta.filters

    assert api.router.plain["/resource"]
    assert api.router.dynamic[0].pattern.pattern == "^/resource/(?P<id>[^/]+)$"


async def test_get(client, ResourceEndpoint, resource):
    res = await client.get("/api/resource")
    assert res.status_code == 200
    json = await res.json()
    assert json[0]["id"] == 1
    assert json[0]["count"] is None
    assert json[0]["name"] == "test"

    res = await client.get("/api/resource/1")
    assert res.status_code == 200
    json = await res.json()
    assert json
    assert json["active"] is False
    assert json["count"] is None
    assert json["created"]
    assert json["id"] == 1
    assert json["name"] == "test"

    res = await client.get("/api/resource/unknown")
    assert res.status_code == 404

    res = await client.get("/api/resource/action?custom=123")
    assert res.status_code == 200
    json = await res.json()
    assert json


async def test_create(client, ResourceEndpoint):
    res = await client.post("/api/resource", json={"active": True})
    assert res.status_code == 400
    json = await res.json()
    assert json["errors"]
    assert "name" in json["errors"]

    res = await client.post("/api/resource", data={"name": "test2", "active": True})
    assert res.status_code == 200
    json = await res.json()
    assert json["id"] == 1
    assert json["name"] == "test2"
    assert json["active"]


async def test_edit(client, resource, ResourceEndpoint):
    res = await client.put("/api/resource/1", data={"name": "new"})
    assert res.status_code == 200
    json = await res.json()
    assert json["name"] == "new"
    assert json["id"] == 1


# TODO: databases have a bug with id.in_
# https://github.com/encode/databases/pull/378
@pytest.mark.skip("Skip while databases has a bug")
async def test_delete(client, resource, ResourceEndpoint, db, Resource):
    res = await client.delete("/api/resource/1")
    assert res.status_code == 200
    json = await res.json()
    assert not json

    assert not await db.fetch_one(Resource.select().where(Resource.c.id == 1))


async def test_sort(client, ResourceEndpoint, db, Resource):
    await db.execute_many(
        Resource.insert(),
        [
            {"name": "test4", "count": 2},
            {"name": "test3", "count": 3},
            {"name": "test2", "count": 1},
        ],
    )

    # Default sort
    res = await client.get("/api/resource")
    assert res.status_code == 200
    json = await res.json()
    assert json[0]["id"] == 3
    assert json[1]["id"] == 2

    res = await client.get("/api/resource?sort=-count")
    assert res.status_code == 200
    json = await res.json()
    assert json[0]["id"] == 2
    assert json[1]["id"] == 1


# TODO: databases have a bug with id.in_
# https://github.com/encode/databases/pull/378
@pytest.mark.skip("Skip while databases has a bug")
async def test_filters(client, ResourceEndpoint, db, Resource):
    await db.execute_many(
        Resource.insert(),
        [
            {"name": "test4", "count": 2},
            {"name": "test3", "count": 3},
            {"name": "test2", "count": 1},
        ],
    )

    res = await client.get('/api/resource?where={"name":"test"}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 0

    res = await client.get('/api/resource?where={"name": {"$in": ["test3", "test2"]}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 2

    res = await client.get('/api/resource?where={"oid": {"$in": [2, 3]}}')
    assert res.status_code == 200
    json = await res.json()
    assert [d["id"] for d in json] == [3, 2]

    res = await client.get('/api/resource?where={"name": {"$starts": "test"}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 3

    res = await client.get('/api/resource?where={"name": {"$ends": "3"}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 1

    res = await client.get('/api/resource?where={"oid": {"$between": [1, 3]}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 3

    res = await client.get('/api/resource?where={"oid": {"$gt": "2"}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 1


async def test_paginate(client, ResourceEndpoint, db, Resource):
    await db.execute_many(Resource.insert(), [{"name": "test%d" % n} for n in range(12)])

    res = await client.get("/api/resource")
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 10

    res = await client.get("/api/resource?limit=5")
    assert res.status_code == 200
    assert res.headers["x-total"] == "12"
    assert res.headers["x-limit"] == "5"
    assert res.headers["x-offset"] == "0"
    json = await res.json()
    assert len(json) == 5

    res = await client.get("/api/resource?limit=5&offset=9")
    assert res.status_code == 200
    assert res.headers["x-total"] == "12"
    assert res.headers["x-limit"] == "5"
    assert res.headers["x-offset"] == "9"
    json = await res.json()
    assert len(json) == 3


# TODO: databases have a bug with id.in_
# https://github.com/encode/databases/pull/378
@pytest.mark.skip("Skip while databases has a bug")
async def test_batch_ops(client, ResourceEndpoint, db, Resource):
    # Batch operations (only POST/DELETE are supported for now)
    res = await client.post(
        "/api/resource",
        json=[
            {"name": "test3", "active": True},
            {"name": "test4", "active": True},
            {"name": "test6", "active": True},
        ],
    )
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 3
    assert json[0]["id"] == 1
    assert json[1]["id"] == 2
    assert json[2]["id"] == 3

    res = await client.delete("/api/resource", json=[1, 2, 3])
    assert res.status_code == 200

    assert not await db.fetch_all(Resource.select().where(Resource.c.id.in_([1, 2, 3])))


async def test_openapi(client, ResourceEndpoint):
    res = await client.get("/api/openapi.json")
    assert res.status_code == 200
    json = await res.json()
    assert json
