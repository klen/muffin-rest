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


def test_base(app, client):

    @app.register
    class Resource(mr.RESTHandler):

        methods = 'get',

        collection = [1, 2, 3]

        def get_many(self, request):
            return self.collection

        def get_one(self, request):
            resource = yield from super(Resource, self).get_one(request)
            if resource:
                return self.collection[int(resource)]
            return None

        def post(self, request):
            raise Exception('Shouldnt be called')

    response = client.get('/resource')
    assert response.json == ['1', '2', '3']

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

    assert ResourceHandler.form
    assert ResourceHandler.name == 'resource'

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
