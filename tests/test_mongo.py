import marshmallow as ma
import pytest
from bson import ObjectId
from muffin_mongo import Plugin as Mongo


@pytest.fixture(scope='module')
def aiolib():
    return 'asyncio', {'use_uvloop': False}


@pytest.fixture
async def mongo(app):
    return Mongo(app)


@pytest.fixture
async def resources(mongo):
    collection = mongo.tests.resources
    yield collection
    await collection.drop()


@pytest.fixture
def ResourceEndpoint(api, resources):
    from muffin_rest.mongo import MongoRESTHandler

    @api.route
    class ResourceHandler(MongoRESTHandler):

        class Meta:
            limit = 10
            collection = resources
            filters = 'active', 'name', ('oid', {'field': '_id'}),
            sorting = ('name', {'default': 'asc'}), 'count'
            schema_fields = {
                'active': ma.fields.Bool(default=False),
                'name': ma.fields.String(required=True),
                'count': ma.fields.Integer(),
            }

        @MongoRESTHandler.route('/resource/action')
        async def action(self, request, resource=None):
            rows = await self.meta.collection.find().to_list(None)
            return await self.dump(request, rows)

    return ResourceHandler


@pytest.fixture
async def resource(resources):
    res = await resources.insert_one({'name': 'test'})
    return res.inserted_id


def test_imports():
    from muffin_rest import MongoRESTHandler, MongoFilter, MongoFilters, MongoSort, MongoSorting

    assert MongoRESTHandler
    assert MongoFilter
    assert MongoFilters
    assert MongoSort
    assert MongoSorting


async def test_base(api, ResourceEndpoint):
    assert ResourceEndpoint
    assert ResourceEndpoint.meta.name == 'resource'
    assert ResourceEndpoint.meta.Schema

    assert api.router.plain['/resource']
    assert api.router.dynamic[0].pattern.pattern == '^/resource/(?P<resource>[^/]+)$'


async def test_get(client, ResourceEndpoint, resource):
    res = await client.get('/api/resource')
    assert res.status_code == 200
    json = await res.json()
    assert json[0]['_id'] == str(resource)
    assert not json[0]['active']
    assert json[0]['name'] == 'test'

    res = await client.get(f"/api/resource/{ resource }")
    assert res.status_code == 200
    json = await res.json()
    assert json
    assert json['_id']
    assert not json['active']
    assert json['name'] == 'test'

    res = await client.get('/api/resource/unknown')
    assert res.status_code == 404

    res = await client.get('/api/resource/action?custom=123')
    assert res.status_code == 200
    json = await res.json()
    assert json


async def test_create(client, ResourceEndpoint):
    res = await client.post('/api/resource', json={'active': True})
    assert res.status_code == 400
    json = await res.json()
    assert json['errors']
    assert 'name' in json['errors']

    res = await client.post('/api/resource', data={'name': 'test2', 'active': True})
    assert res.status_code == 200
    json = await res.json()
    assert json['_id']
    assert json['name'] == 'test2'
    assert json['active']


async def test_edit(client, resource, ResourceEndpoint):
    res = await client.put(f"/api/resource/{resource}", data={'name': 'new'})
    assert res.status_code == 200
    json = await res.json()
    assert json['name'] == 'new'
    assert json['_id'] == str(resource)


async def test_delete(client, resource, ResourceEndpoint, resources):
    res = await client.delete(f"/api/resource/{ resource }")
    assert res.status_code == 200
    json = await res.json()
    assert not json

    assert not await resources.find_one({'_id': resource})
    assert await resources.count_documents({}) == 0


async def test_sort(client, ResourceEndpoint, resources):
    await resources.insert_many([
        {'name': 'test4', 'count': 2},
        {'name': 'test3', 'count': 3},
        {'name': 'test2', 'count': 1},
    ])

    # Default sort by name
    res = await client.get('/api/resource')
    assert res.status_code == 200
    json = await res.json()
    assert json[0]['name'] == 'test2'
    assert json[1]['name'] == 'test3'

    res = await client.get('/api/resource?sort=-count')
    assert res.status_code == 200
    json = await res.json()
    assert json[0]['count'] == 3
    assert json[1]['count'] == 2


async def test_filters(client, ResourceEndpoint, resources):
    await resources.insert_many([
        {'name': 'test4', 'count': 2},
        {'name': 'test3', 'count': 3},
        {'name': 'test2', 'count': 1},
    ])
    res = await client.get('/api/resource?where={"name":"test"}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 0

    res = await client.get('/api/resource?where={"name": {"$in": ["test3", "test2"]}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 2

    res = await client.get('/api/resource?where={"name": {"$starts": "test"}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 3

    res = await client.get('/api/resource?where={"name": {"$ends": "3"}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 1

    _id = json[0]['_id']

    res = await client.get('/api/resource?where={"oid": "%s"}' % _id)
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 1


async def test_paginate(client, ResourceEndpoint, resources):
    await resources.insert_many([
        {'name': 'test%d' % n} for n in range(12)
    ])

    res = await client.get('/api/resource')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 10

    res = await client.get('/api/resource?limit=5')
    assert res.status_code == 200
    assert res.headers['x-total'] == '12'
    assert res.headers['x-limit'] == '5'
    assert res.headers['x-offset'] == '0'
    json = await res.json()
    assert len(json) == 5

    res = await client.get('/api/resource?limit=5&offset=9')
    assert res.status_code == 200
    assert res.headers['x-total'] == '12'
    assert res.headers['x-limit'] == '5'
    assert res.headers['x-offset'] == '9'
    json = await res.json()
    assert len(json) == 3


async def test_batch_ops(client, ResourceEndpoint, resources):
    # Batch operations (only POST/DELETE are supported for now)
    res = await client.post('/api/resource', json=[
        {'name': 'test3', 'active': True},
        {'name': 'test4', 'active': True},
        {'name': 'test6', 'active': True},
    ])
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 3
    assert json[0]['_id']
    assert json[1]['_id']
    assert json[2]['_id']

    res = await client.delete('/api/resource', json=[item['_id'] for item in json])
    assert res.status_code == 200

    assert not await resources.find(
        {'_id': {"$in": list(map(ObjectId, [item['_id'] for item in json]))}}).to_list(None)


async def test_openapi(client, ResourceEndpoint):
    res = await client.get('/api/openapi.json')
    assert res.status_code == 200
    json = await res.json()
    assert json
