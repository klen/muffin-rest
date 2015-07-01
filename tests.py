import muffin as m
import pytest
import datetime as dt

import muffin_rest as mr


@pytest.fixture(scope='session')
def app(loop, request):
    return m.Application(
        'rest', loop=loop, PLUGINS=['muffin_peewee'], PEEWEE_CONNECTION='sqlite:///:memory:')


@pytest.fixture(autouse=True)
def clean_app(app, request):
    @request.addfinalizer
    def _():
        app.router._routes.clear()
        app.router._urls = []
        m.Handler.handlers = set()


def test_api(app, client):
    api = mr.Api(app, '/api/v1', scheme='map')
    assert api.prefix == '/api/v1'
    assert api.prefix_name == 'api-v1'

    @api.register
    class Resource(mr.RESTHandler):
        methods = 'get',

    @api.register('/cfg')
    def cfg(request):
        return {'VAR': 'VALUE'}

    assert 'api-v1-resource-*' in api.urls.router

    client.get('/api/v1/unknown', status=404)

    response = client.get('/api/v1/resource')
    assert response.json == []

    response = client.get('/api/v1/map')
    assert response.json

    response = client.get('/api/v1/cfg')
    assert response.json


def test_base(app, client):

    class NumFilter(mr.IntegerFilter):
        def apply(self, collection, value):
            return [o for o in collection if o == value]

    @app.register(name='api-resource')
    class Resource(mr.RESTHandler):

        methods = 'get',

        collection = [1, 2, 3]

        filters = NumFilter('num'),

        def get_many(self, request):
            return self.collection

        def get_one(self, request):
            resource = yield from super(Resource, self).get_one(request)
            if resource:
                return self.collection[int(resource)]
            return None

        def post(self, request):
            raise Exception('Shouldnt be called')

    assert 'api-resource-*' in app.router
    response = client.get('/resource')
    assert response.json == ['1', '2', '3']

    response = client.get('/resource?mr-num=1')
    assert response.json == ['1']

    response = client.get('/resource/2')
    assert response.text == '3'

    client.post('/resource', status=405)


def test_peewee(app, client):
    import peewee as pw

    @app.ps.peewee.register
    class Resource(app.ps.peewee.TModel):
        active = pw.BooleanField(default=False)
        name = pw.CharField(null=False)

    Resource.create_table()

    from muffin_rest.peewee import PWRESTHandler

    @app.register
    class ResourceHandler(PWRESTHandler):
        model = Resource
        filters = 'active', 'name'

    assert ResourceHandler.form
    assert ResourceHandler.name == 'resource'
    assert 'rest-resource-*' in app.router

    response = client.get('/resource')
    assert response.json == []

    Resource(name='test').save()
    response = client.get('/resource')
    assert response.json

    response = client.get('/resource/1')
    assert response.json['id'] == 1
    assert response.json['name'] == 'test'

    response = client.post('/resource', {
        'name': 'test2', 'created': '2010-01-01 00:00:00', 'active': True})
    assert response.json['id'] == 2
    assert response.json['name'] == 'test2'
    assert response.json['active']
    created = dt.datetime.fromtimestamp(response.json['created'])
    assert created.year == 2010

    response = client.patch('/resource/2', {'name': 'new'})
    assert response.json['id'] == 2
    assert response.json['name'] == 'new'
    assert response.json['active']
    created = dt.datetime.fromtimestamp(response.json['created'])
    assert created.year == 2010

    response = client.delete('/resource/2', {'name': 'new'})
    assert response.text == ''
    assert Resource.select().where(Resource.id == 1).exists()
    assert not Resource.select().where(Resource.id == 2).exists()

    Resource(name='test2').save()
    Resource(name='test3').save()
    Resource(name='test4').save()
    response = client.get('/resource?mr-name=test')
    assert len(response.json) == 1
