import collections
import datetime as dt

import muffin
import pytest
from aiohttp import MultiDict

import muffin_rest as mr


@pytest.fixture(scope='session')
def app(loop, request):
    return muffin.Application(
        'rest', loop=loop, PLUGINS=['muffin_peewee'], PEEWEE_CONNECTION='sqlite:///:memory:')


@pytest.fixture(autouse=True)
def clean_app(app, request):
    @request.addfinalizer
    def _():
        app.router._resources.clear()
        muffin.Handler.handlers = set()


def test_base(app, client):

    collection = list(range(10))

    @app.register(name='api.resource')
    class Resource(mr.RESTHandler):

        methods = 'get',

        class Meta:
            filters = 'num',
            per_page = 3

        def get_many(self, request, **kwargs):
            return collection

        def get_one(self, request, **kwargs):
            resource = yield from super(Resource, self).get_one(request, **kwargs)
            if resource:
                return self.collection[int(resource)]
            return None

        def post(self, request, **kwargs):
            raise Exception('Should never be called')

    assert 'api.resource' in app.router
    response = client.get('/resource?some=22')
    assert response.json == [0, 1, 2]
    assert response.headers['X-TOTAL-COUNT'] == '10'
    assert response.headers['X-Limit'] == '3'
    assert response.headers['Link']

    response = client.get('/resource?where={"num":1}')
    assert response.json == [1]

    response = client.get('/resource?where={"num":{"$gt":3}}')
    assert response.json == [4, 5, 6]

    response = client.get('/resource/2')
    assert response.json == 2

    client.post('/resource', status=405)


def test_api(app, client):
    api = mr.Api(app, '/api/v1', scheme='map')
    assert api.prefix == '/api/v1'
    assert api.prefix_name == 'api.v1'

    @api.register
    class Resource(mr.RESTHandler):
        methods = 'get',

    @Resource.register('%s/action' % api.prefix)
    def resource_action(hander, request, resource=None):
        return 'ACTION'

    @api.register('/cfg')
    def cfg(request):
        return {'VAR': 'VALUE'}

    assert 'resource' in api.resource.router

    client.get('/api/v1/unknown', status=404)

    response = client.get('/api/v1/resource')
    assert response.json == []

    response = client.get('/api/v1/map')
    assert response.json

    response = client.get('/api/v1/cfg')
    assert response.json

    response = client.get('/api/v1/action')
    assert response.json == 'ACTION'


def test_peewee(app, client):
    import peewee as pw
    from muffin_peewee.fields import JSONField

    @app.ps.peewee.register
    class Resource(app.ps.peewee.TModel):
        active = pw.BooleanField(default=False)
        name = pw.CharField(null=False)
        count = pw.IntegerField(null=True)
        config = JSONField(default={})

    Resource.create_table()

    from muffin_rest.peewee import PWRESTHandler
    from marshmallow_peewee import Timestamp

    @app.register('/resource', r'/resource/{resource:\d+}')
    class ResourceHandler(PWRESTHandler):

        class Meta:
            model = Resource
            schema = dict(created=Timestamp())
            filters = 'active', 'name', 'id',

    assert ResourceHandler.Schema
    assert ResourceHandler.name == 'resource'
    assert 'rest.resource' in app.router

    response = client.get('/resource')
    assert response.json == []

    Resource(name='test').save()
    response = client.get('/resource')
    assert response.json

    response = client.get('/resource/1')
    assert response.json['id'] == 1
    assert response.json['name'] == 'test'

    @ResourceHandler.register('/resource/action')
    def action(handler, request, resource=None):
        return list(handler.collection)

    response = client.get('/resource/action?custom=123')
    assert response.json

    response = client.post('/resource', {'active': True}, status=400)
    assert response.json['errors']
    assert 'name' in response.json['errors']

    response = client.post('/resource', {
        'name': 'test2', 'created': 1000000, 'active': True})
    assert response.json['id'] == 2
    assert response.json['name'] == 'test2'
    assert response.json['active']
    created = dt.datetime.fromtimestamp(response.json['created'])
    assert created.year == 1970

    response = client.patch('/resource/2', {'name': 'new'})
    assert response.json['id'] == 2
    assert response.json['name'] == 'new'
    assert response.json['active']
    created = dt.datetime.fromtimestamp(response.json['created'])
    assert created.year == 1970

    response = client.delete('/resource/2', {'name': 'new'})
    assert response.text == 'null'
    assert Resource.select().where(Resource.id == 1).exists()
    assert not Resource.select().where(Resource.id == 2).exists()

    Resource(name='test2').save()
    Resource(name='test3').save()
    Resource(name='test4').save()
    response = client.get('/resource?where={"name":"test"}')
    assert len(response.json) == 1

    response = client.get('/resource?where={"name": {"$in": ["test", "test2"]}}')
    assert len(response.json) == 2

    response = client.get('/resource?where={"id": {"$gt": 2}}')
    assert len(response.json) == 2

    for n in range(6):
        Resource(name='test%d' % n).save()

    response = client.get('/resource')
    assert len(response.json) == 10

    response = client.get('/resource?per_page=3')
    assert len(response.json) == 3

    response = client.get('/resource?per_page=1')
    assert response.headers['x-page-last'] == '9'
    assert response.headers['x-total-count'] == '10'

#  pylama:ignore=W0621,W0612
