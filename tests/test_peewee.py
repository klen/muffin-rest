import peewee as pw
from muffin_peewee import Plugin as Peewee, JSONField
import pytest


@pytest.fixture
async def db(app):
    return Peewee(app, connection='sqlite+async:///:memory:', manage_connections=False)


@pytest.fixture
async def Resource(db):

    @db.register
    class Resource(pw.Model):
        active = pw.BooleanField(default=False)
        name = pw.CharField(null=False)
        count = pw.IntegerField(null=True)
        config = JSONField(default={})

    Resource.create_table()
    return Resource


@pytest.fixture
async def ResourceEndpoint(Resource, api):
    from muffin_rest.peewee import PWRESTHandler

    @api.route
    class ResourceEndpoint(PWRESTHandler):

        class Meta:
            filters = 'active', 'name', ('oid', {'field': 'id'}),
            limit = 10
            model = Resource
            sorting = ('id', {'default': 'desc'}), 'name', Resource.count

        @PWRESTHandler.route('/resource/action')
        async def action(self, request, resource=None):
            """Description for the action."""
            return await self.dump(request, list(self.collection))

    return ResourceEndpoint


@pytest.fixture
async def resource(Resource):
    return Resource.create(name='test')


def test_imports():
    from muffin_rest import PWRESTHandler, PWFilter, PWFilters, PWSort, PWSorting

    assert PWRESTHandler
    assert PWFilter
    assert PWFilters
    assert PWSort
    assert PWSorting


async def test_base(api, ResourceEndpoint, Resource):
    assert ResourceEndpoint
    assert ResourceEndpoint.meta.name == 'resource'
    assert ResourceEndpoint.meta.Schema
    assert ResourceEndpoint.meta.sorting
    assert list(ResourceEndpoint.meta.sorting.mutations.keys()) == ['id', 'name', 'count']
    assert ResourceEndpoint.meta.sorting.default == [Resource.id.desc()]

    assert api.router.plain['/resource']
    assert api.router.dynamic[0].pattern.pattern == '^/resource/(?P<id>[^/]+)$'


async def test_api_get(client, ResourceEndpoint, resource):
    res = await client.get('/api/resource')
    assert res.status_code == 200
    json = await res.json()
    assert json
    assert json[0]['id'] == '1'
    assert json[0]['count'] is None
    assert json[0]['name'] == 'test'
    assert json[0]['config'] == {}

    res = await client.get('/api/resource/1')
    assert res.status_code == 200
    assert await res.json() == {
        'active': False,
        'config': {},
        'count': None,
        'id': '1',
        'name': 'test',
    }

    res = await client.get('/api/resource/unknown')
    assert res.status_code == 404
    assert await res.json() == {'error': True, 'message': 'Resource not found'}

    res = await client.get('/api/resource/action?custom=123')
    assert res.status_code == 200
    json = await res.json()
    assert json


async def test_api_create(client, ResourceEndpoint):
    res = await client.post('/api/resource', json={'active': True})
    assert res.status_code == 400
    json = await res.json()
    assert json['errors']
    assert 'name' in json['errors']

    res = await client.post('/api/resource', data={'name': 'test2', 'active': True, 'unknown': 22})
    assert res.status_code == 200
    json = await res.json()
    assert json['id'] == '1'
    assert json['name'] == 'test2'
    assert json['active']


async def test_api_edit(client, resource, ResourceEndpoint):
    res = await client.put('/api/resource/1', data={'name': 'new'})
    assert res.status_code == 200
    json = await res.json()
    assert json['name'] == 'new'
    assert json['id'] == '1'


async def test_api_delete(client, resource, ResourceEndpoint, Resource):
    res = await client.delete('/api/resource/1')
    assert res.status_code == 200
    json = await res.json()
    assert not json

    assert not Resource.select().where(Resource.id == 1).exists()


async def test_api_sort(client, ResourceEndpoint, Resource):
    Resource.create(name='test2', count=2)
    Resource.create(name='test3', count=3)
    Resource.create(name='test4', count=1)

    # Default sort
    res = await client.get('/api/resource')
    assert res.status_code == 200
    json = await res.json()
    assert json[0]['id'] == '3'
    assert json[1]['id'] == '2'

    res = await client.get('/api/resource?sort=-count')
    assert res.status_code == 200
    json = await res.json()
    assert json[0]['id'] == '2'
    assert json[1]['id'] == '1'


async def test_api_filters(client, ResourceEndpoint, Resource):
    Resource.create(name='test2', count=2)
    Resource.create(name='test3', count=3)
    Resource.create(name='test4', count=1)

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

    res = await client.get('/api/resource?where={"oid": {"$between": ["2", "3"]}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 2

    res = await client.get('/api/resource?where={"oid": {"$gt": "2"}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 1


async def test_api_paginate(client, ResourceEndpoint, Resource):
    for n in range(12):
        Resource.create(name='test%d' % n)

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


async def test_batch_ops(client, ResourceEndpoint, db, Resource):
    # Batch operations (only POST/DELETE are supported for now)
    res = await client.post('/api/resource', json=[
        {'name': 'test3', 'active': True},
        {'name': 'test4', 'active': True},
        {'name': 'test6', 'active': True},
    ])
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 3
    assert json[0]['id'] == '1'
    assert json[1]['id'] == '2'
    assert json[2]['id'] == '3'

    res = await client.delete('/api/resource', json=['1', '2', '3'])
    assert res.status_code == 200

    assert not Resource.select().where(Resource.id << ('11', '12', '13')).count()


async def test_openapi(client, ResourceEndpoint):
    res = await client.get('/api/openapi.json')
    assert res.status_code == 200
    json = await res.json()
    assert json
