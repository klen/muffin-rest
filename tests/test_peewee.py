from enum import Enum
from typing import Any

import peewee as pw
import pytest
from muffin_peewee import JSONLikeField
from muffin_peewee import Plugin as Peewee
from muffin_peewee.fields import StrEnumField


@pytest.fixture(scope="module")
def aiolib():
    return "asyncio", {"use_uvloop": False}


@pytest.fixture(scope="session", autouse=True)
def _setup_logging():
    import logging

    logger = logging.getLogger("peewee")
    logger.setLevel(logging.DEBUG)


@pytest.fixture
async def db(app):
    db = Peewee(app, connection="sqlite:///:memory:", auto_connection=False)
    async with db, db.connection():
        yield db


class Statuses(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Group(pw.Model):
    name = pw.CharField(null=True)


class Resource(pw.Model):
    id = pw.AutoField()
    active = pw.BooleanField(default=False)
    name = pw.CharField(null=False)
    count = pw.IntegerField(null=True)
    config: Any = JSONLikeField(default={})
    status = StrEnumField(Statuses, default=Statuses.ACTIVE)

    group = pw.ForeignKeyField(Group, null=True)


@pytest.fixture(autouse=True)
async def init(db):
    db.manager.register(Resource)
    await db.manager.create_tables(Resource)
    return Resource


@pytest.fixture
async def endpoint_cls(api):
    from muffin_rest.peewee import PWRESTHandler

    @api.route
    class ResourceEndpoint(PWRESTHandler[Resource]):
        class Meta:
            filters = ("active", "name", "group_id", ("oid", {"field": "id"}), "count")
            limit = 10
            model = Resource
            sorting = (("id", {"field": Resource.id, "default": "desc"}), "name", Resource.count)
            delete_recursive = True

        @PWRESTHandler.route("/resource/action")
        async def action(self, request, resource=None):
            """Description for the action."""
            resources = await self.meta.manager.fetchall(self.collection)
            return await self.dump(request, resources, many=True)

    return ResourceEndpoint


@pytest.fixture
async def resource(db):
    return await db.manager.create(Resource, name="test")


def test_imports():
    from muffin_rest import PWFilter, PWFilters, PWRESTHandler, PWSort, PWSorting
    from muffin_rest.peewee import PWRESTBase

    assert PWRESTHandler is not None
    assert PWFilter is not None
    assert PWFilters is not None
    assert PWSort is not None
    assert PWSorting is not None
    assert PWRESTBase is not None


async def test_base(api, endpoint_cls):
    assert endpoint_cls
    assert endpoint_cls.meta.name == "resource"
    assert endpoint_cls.meta.manager

    # Schema
    assert endpoint_cls.meta.Schema
    assert endpoint_cls.meta.Schema._declared_fields
    ff = endpoint_cls.meta.Schema._declared_fields["active"]
    assert ff.load_default is False

    from muffin_rest.peewee.schemas import EnumField

    ef = endpoint_cls.meta.Schema._declared_fields["status"]
    assert isinstance(ef, EnumField)

    # Sorting
    assert endpoint_cls.meta.sorting
    assert list(endpoint_cls.meta.sorting.mutations.keys()) == ["id", "name", "count"]
    assert endpoint_cls.meta.sorting.default == [Resource.id.desc()]

    assert api.router.plain["/resource"]
    assert api.router.dynamic[0].pattern.pattern == "^/resource/(?P<id>[^/]+)$"
    assert "group_id" in endpoint_cls.meta.filters.mutations


async def test_get(client, endpoint_cls, resource):
    res = await client.get("/api/resource")
    assert res.status_code == 200
    json = await res.json()
    assert json
    assert json[0]["config"] == {}
    assert json[0]["count"] is None
    assert json[0]["id"] == "1"
    assert json[0]["name"] == "test"

    res = await client.get("/api/resource/1")
    assert res.status_code == 200
    assert await res.json() == {
        "active": False,
        "config": {},
        "status": "active",
        "count": None,
        "id": "1",
        "name": "test",
        "group": None,
    }

    res = await client.get("/api/resource/unknown")
    assert res.status_code == 404
    assert await res.json() == {"error": True, "message": "Resource not found"}

    res = await client.get("/api/resource/action?custom=123")
    assert res.status_code == 200
    json = await res.json()
    assert json


async def test_create(client, endpoint_cls):
    res = await client.post("/api/resource", json={"active": True})
    assert res.status_code == 400
    json = await res.json()
    assert json["errors"]
    assert "name" in json["errors"]

    res = await client.post("/api/resource", data={"name": "test2", "active": True, "unknown": 22})
    assert res.status_code == 200
    json = await res.json()
    assert json["id"] == "1"
    assert json["name"] == "test2"
    assert json["active"]


async def test_edit(client, resource, endpoint_cls):
    res = await client.put("/api/resource/1", data={"name": "new", "status": "inactive"})
    json = await res.json()
    assert json["name"] == "new"
    assert json["id"] == "1"
    assert json["status"] == "inactive"
    assert res.status_code == 200

    res = await client.put("/api/resource/1", data={"name": "new", "status": "unknown"})
    assert res.status_code == 400
    json = await res.json()
    assert json["errors"]


async def test_delete(client, resource, endpoint_cls, db):
    res = await client.delete(f"/api/resource/{resource.id}")
    assert res.status_code == 200
    json = await res.json()
    assert json == resource.get_id()

    assert not await db.manager.fetchone(Resource.select().where(Resource.id == resource.id))


async def test_sort(apiclient, endpoint_cls, db):
    await db.manager.create(Resource, name="test2", count=2)
    await db.manager.create(Resource, name="test3", count=3)
    await db.manager.create(Resource, name="test4", count=1)

    # Default sort
    res = await apiclient.get("/api/resource")
    assert res.status_code == 200
    json = await res.json()
    assert json[0]["id"] == "3"
    assert json[1]["id"] == "2"

    res = await apiclient.get("/api/resource", sort="-count")
    assert res.status_code == 200
    json = await res.json()
    assert json[0]["id"] == "2"
    assert json[1]["id"] == "1"


async def test_filters(apiclient, endpoint_cls, db):
    await db.manager.create(Resource, name="test2", count=2)
    await db.manager.create(Resource, name="test3", count=3)
    await db.manager.create(Resource, name="test4", count=1)
    await db.manager.create(Resource, name="name5", count=4)
    await db.manager.create(Resource, name="name6", count=5)

    res = await apiclient.get("/api/resource", filters={"name": "test"})
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 0

    res = await apiclient.get("/api/resource", filters={"name": {"$in": ["test3", "test2"]}})
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 2

    res = await apiclient.get("/api/resource", filters={"name": {"$starts": "test"}})
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 3

    res = await apiclient.get("/api/resource", filters={"name": {"$ends": "3"}})
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 1

    res = await apiclient.get("/api/resource", filters={"oid": {"$between": ["2", "3"]}})
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 2

    res = await apiclient.get("/api/resource", filters={"oid": {"$gt": "2"}})
    assert res.status_code == 200
    json = await res.json()
    for data in json:
        assert int(data["id"]) > 2

    res = await apiclient.get(
        "/api/resource",
        filters={"count": {"$or": [{"$between": ["1", "2"]}, {"$between": ["4", "5"]}]}},
    )
    assert res.status_code == 200
    json = await res.json()
    for data in json:
        assert data["count"] in [1, 2, 4, 5]


async def test_paginate(apiclient, endpoint_cls, db):
    for n in range(12):
        await db.manager.create(Resource, name=f"test{n}")

    res = await apiclient.get("/api/resource")
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 10

    res = await apiclient.get("/api/resource", limit=5)
    assert res.status_code == 200
    assert res.headers["x-total"] == "12"
    assert res.headers["x-limit"] == "5"
    assert res.headers["x-offset"] == "0"
    json = await res.json()
    assert len(json) == 5

    res = await apiclient.get("/api/resource", limit=5, offset=9)
    assert res.status_code == 200
    assert res.headers["x-total"] == "12"
    assert res.headers["x-limit"] == "5"
    assert res.headers["x-offset"] == "9"
    json = await res.json()
    assert len(json) == 3


async def test_batch_ops(client, endpoint_cls, db):
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
    assert json[0]["id"] == "1"
    assert json[1]["id"] == "2"
    assert json[2]["id"] == "3"

    res = await client.delete("/api/resource", json=["1", "2", "3"])
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 3
    assert json[0] == 1
    assert json[1] == 2
    assert json[2] == 3

    assert not await db.manager.count(
        Resource.select().where(Resource.id << ("11", "12", "13")),
    )


async def test_openapi(client, endpoint_cls):
    res = await client.get("/api/openapi.json")
    assert res.status_code == 200
    json = await res.json()
    assert json


async def test_endpoint_inheritance():
    from muffin_rest.peewee import PWRESTHandler

    class ResourceEndpoint(PWRESTHandler):
        class Meta:
            model = Resource

    assert ResourceEndpoint.meta.name == "resource"

    class ChildEndpoint(ResourceEndpoint):
        class Meta:
            name = "child"

    assert ChildEndpoint.meta.name == "child"


async def test_custom_filter():
    from muffin_rest.peewee.filters import PWFilter

    class CustomFilter(PWFilter):
        field = Resource.count

    flt = CustomFilter("count")
    assert flt
    assert flt.field
    assert flt.field is Resource.count

    assert CustomFilter.field


async def test_aiomodels(client, db, api):
    events = []

    class TestModel(db.Model):
        data = pw.CharField()

        async def save(self, **kwargs):
            events.append("custom-save")
            return await super().save(**kwargs)

        async def delete_instance(self, **kwargs):
            events.append("custom-delete")
            return await super().delete_instance(**kwargs)

    await db.manager.create_tables(TestModel)

    from muffin_rest.peewee import PWRESTHandler

    @api.route
    class Test(PWRESTHandler):
        class Meta(PWRESTHandler.Meta):
            model = TestModel

    res = await client.post("/api/testmodel", json={"data": "test"})
    assert res.status_code == 200
    json = await res.json()
    assert json["id"]

    assert events
    assert "custom-save" in events

    res = await client.delete(f"/api/testmodel/{json['id']}")
    assert res.status_code == 200

    assert "custom-delete" in events


async def test_custom_pk(db, api, client):
    class CustomPKModel(db.Model):
        id = pw.CharField(default="custom-id", primary_key=True)
        body = pw.TextField()

    await db.manager.create_tables(CustomPKModel)

    from muffin_rest.peewee import PWRESTHandler

    @api.route("/custom-pk", "/custom-pk/{id}")
    class CustomPKTest(PWRESTHandler):
        class Meta(PWRESTHandler.Meta):
            model = CustomPKModel

    res = await client.post("/api/custom-pk", json={"id": "test-id", "body": "test body"})
    assert res.status_code == 200
    json = await res.json()
    assert json["id"]

    assert await CustomPKModel.select().count() == 1
    res = await CustomPKModel.get(CustomPKModel.id == "test-id")
    assert res.body == "test body"

    res = await client.put("/api/custom-pk/test-id", json={"body": "updated body"})
    assert res.status_code == 200
    json = await res.json()
    assert json["body"] == "updated body"

    res = await CustomPKModel.get(CustomPKModel.id == "test-id")
    assert res.body == "updated body"
