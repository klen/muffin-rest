import collections
import math
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


def test_filters():
    filters = (
        'one', ('two', {'filter_name': 'two__gt', 'op': '>'}),
        mr.Filter('three'), ('dummy', {'op': None}),
    )
    form = mr.FilterForm(prefix='test-')
    filters = [mr.default_converter(None, flt).bind(form) for flt in filters]
    assert form._fields
    assert 'one' in form._fields
    assert 'two__gt' in form._fields
    assert 'three' in form._fields
    assert 'dummy' in form._fields

    Model = collections.namedtuple('Model', ('one', 'two', 'three'))

    collection = [Model(1, 2, 3), Model(4, 5, 6), Model(7, 8, 9)]
    test = form.process(collection, MultiDict({'one': 1}))
    assert test == collection
    assert not form.filters

    test = form.process(collection, MultiDict({'test-one': 1}))
    assert len(test) == 1
    assert form.filters == {'one': 1}

    test = form.process(collection, MultiDict({'test-two__gt': 2}))
    assert len(test) == 2
    assert form.filters == {'two': 2}

    test = form.process(collection, MultiDict({'test-dummy': 42}))
    assert test == collection
    assert form.filters == {'dummy': 42}


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


def test_base(app, client):

    class NumFilter(mr.IntegerFilter):
        def apply(self, collection, value):
            return [o for o in collection if self.op(o, value)]

    @app.register(name='api.resource')
    class Resource(mr.RESTHandler):

        methods = 'get',

        collection = [1, 2, 3, 4, 5]

        filters = NumFilter('num'), NumFilter('num__gte', op='>=')

        limit = 3

        def get_many(self, request):
            return self.collection

        def get_one(self, request):
            resource = yield from super(Resource, self).get_one(request)
            if resource:
                return self.collection[int(resource)]
            return None

        def post(self, request):
            raise Exception('Shouldnt be called')

    assert 'api.resource' in app.router
    response = client.get('/resource?some=22')
    assert response.json == ['1', '2', '3']
    assert response.headers['X-TOTAL-COUNT'] == '5'
    assert response.headers['X-Limit'] == '3'
    assert response.headers['Link']

    response = client.get('/resource?mr-num=1')
    assert response.json == ['1']

    response = client.get('/resource?mr-num__gte=3')
    assert response.json == ['3', '4', '5']

    response = client.get('/resource/2')
    assert response.json == '3'

    client.post('/resource', status=405)


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

    from muffin_rest.peewee import PWRESTHandler, PWMultiFilter

    @app.register('/resource', r'/resource/{resource:\d+}')
    class ResourceHandler(PWRESTHandler):
        model = Resource
        filters = (
            'active', 'name',                                # Simple filters by name (equals)
            ('id', {'filter_name': 'id__gte', 'op': '>='}),  # Filter id by >=
            PWMultiFilter('name', 'name__in'),               # Multivalue filter
            ('custom', {'op': None}),                        # Dummy filter (do nothing)
        )

    assert ResourceHandler.form
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

    response = client.get('/resource/action?mr-custom=123')
    assert response.json

    response = client.post('/resource', {'active': True}, status=400)
    assert 'name' in response.json

    response = client.post('/resource', {
        'name': 'test2', 'created': '2010-03-01 00:00:00', 'active': True})
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
    assert response.text == 'null'
    assert Resource.select().where(Resource.id == 1).exists()
    assert not Resource.select().where(Resource.id == 2).exists()

    Resource(name='test2').save()
    Resource(name='test3').save()
    Resource(name='test4').save()
    response = client.get('/resource?mr-name=test')
    assert len(response.json) == 1

    response = client.get('/resource?mr-name__in=test&mr-name__in=test2')
    assert len(response.json) == 2

    response = client.get('/resource?mr-id__gte=2')
    assert len(response.json) == 3

    for n in range(6):
        Resource(name='test%d' % n).save()

    response = client.get('/resource')
    assert len(response.json) == 10

    response = client.get('/resource?mr--limit=3')
    assert len(response.json) == 3

    response = client.get('/resource?mr--limit=1')
    assert response.headers['x-page-last'] == '9'
    assert response.headers['x-total-count'] == '10'

#  pylama:ignore=W0621,W0612
