import peewee as pw
import pytest
from muffin_peewee import Plugin as Peewee, JSONField


@pytest.fixture(scope='module')
def aiolib():
    return 'asyncio', {'use_uvloop': False}


@pytest.fixture(scope='session', autouse=True)
def setup_logging():
    import logging

    logger = logging.getLogger('peewee')
    logger.setLevel(logging.DEBUG)


@pytest.fixture
async def db(app):
    db = Peewee(app, connection='sqlite:///:memory:', auto_connection=False)
    async with db:
        async with db.connection():
            yield db


@pytest.fixture
async def Resource(db):

    @db.manager.register
    class Resource(pw.Model):
        active = pw.BooleanField(default=False)
        name = pw.CharField(null=False)
        count = pw.IntegerField(null=True)
        config = JSONField(default={})

    assert Resource._manager

    await db.manager.create_tables(Resource)

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
            resources = await self.meta.manager.fetchall(self.collection)
            return await self.dump(request, resources)

    return ResourceEndpoint


@pytest.fixture
async def resource(Resource, db):
    return await db.create(Resource, name='test')


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
    assert ResourceEndpoint.meta.manager

    # Schema
    assert ResourceEndpoint.meta.Schema
    assert ResourceEndpoint.meta.Schema._declared_fields
    ff = ResourceEndpoint.meta.Schema._declared_fields['active']
    assert ff.load_default is False

    # Sorting
    assert ResourceEndpoint.meta.sorting
    assert list(ResourceEndpoint.meta.sorting.mutations.keys()) == ['id', 'name', 'count']
    assert ResourceEndpoint.meta.sorting.default == [Resource.id.desc()]

    assert api.router.plain['/resource']
    assert api.router.dynamic[0].pattern.pattern == '^/resource/(?P<id>[^/]+)$'


async def test_get(client, ResourceEndpoint, resource):
    res = await client.get('/api/resource')
    assert res.status_code == 200
    json = await res.json()
    assert json
    assert json[0]['config'] == {}
    assert json[0]['count'] is None
    assert json[0]['id'] == '1'
    assert json[0]['name'] == 'test'

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


async def test_create(client, ResourceEndpoint):
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


async def test_edit(client, resource, ResourceEndpoint):
    res = await client.put('/api/resource/1', data={'name': 'new'})
    assert res.status_code == 200
    json = await res.json()
    assert json['name'] == 'new'
    assert json['id'] == '1'


async def test_delete(client, resource, ResourceEndpoint, Resource, db):
    res = await client.delete('/api/resource/1')
    assert res.status_code == 200
    json = await res.json()
    assert not json

    assert not await db.fetchone(Resource.select().where(Resource.id == 1))


async def test_sort(client, ResourceEndpoint, Resource, db):
    await db.create(Resource, name='test2', count=2)
    await db.create(Resource, name='test3', count=3)
    await db.create(Resource, name='test4', count=1)

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


async def test_filters(client, ResourceEndpoint, Resource, db):
    await db.create(Resource, name='test2', count=2)
    await db.create(Resource, name='test3', count=3)
    await db.create(Resource, name='test4', count=1)

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


async def test_paginate(client, ResourceEndpoint, Resource, db):
    for n in range(12):
        await db.create(Resource, name=f"test{n}")

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

    assert not await db.count(Resource.select().where(Resource.id << ('11', '12', '13')))


async def test_openapi(client, ResourceEndpoint):
    res = await client.get('/api/openapi.json')
    assert res.status_code == 200
    json = await res.json()
    assert json


async def test_endpoint_inheritance(Resource):
    from muffin_rest.peewee import PWRESTHandler

    class ResourceEndpoint(PWRESTHandler):

        class Meta:
            model = Resource

    assert ResourceEndpoint.meta.name == 'resource'

    class ChildEndpoint(ResourceEndpoint):

        class Meta:
            name = 'child'

    assert ChildEndpoint.meta.name == 'child'


async def test_aiomodels(client, db, api):

    events = []

    class TestModel(db.Model):

        data = pw.CharField()

        async def save(self, **kwargs):
            events.append('custom-save')
            return await super().save(**kwargs)

        async def delete_instance(self, **kwargs):
            events.append('custom-delete')
            return await super().delete_instance(**kwargs)

    await db.create_tables(TestModel)

    from muffin_rest.peewee import PWRESTHandler

    @api.route
    class Test(PWRESTHandler):

        class Meta:
            model = TestModel

    res = await client.post('/api/testmodel', json={'data': 'test'})
    assert res.status_code == 200
    json = await res.json()
    assert json['id']

    assert events
    assert 'custom-save' in events

    res = await client.delete(f"/api/testmodel/{json['id']}")
    assert res.status_code == 200

    assert 'custom-delete' in events
