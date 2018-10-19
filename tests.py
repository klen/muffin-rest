import datetime as dt

import muffin
import marshmallow as ma

import muffin_rest as mr


async def test_base(aiohttp_client):

    collection = list(range(10))

    app = muffin.Application('base')

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

    client = await aiohttp_client(app)

    async with client.get('/resource?some=22') as resp:
        assert resp.status == 200
        assert resp.headers['X-TOTAL-COUNT'] == '10'
        assert resp.headers['X-Limit'] == '3'
        assert 'Link' not in resp.headers
        json = await resp.json()
        assert json == [0, 1, 2]

    async with client.get('/resource?where={"num":1}') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json == [1]

    async with client.get('/resource?where={"num":{"$gt":3}}') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json == [4, 5, 6]

    async with client.get('/resource/2') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json == 2

    async with client.get('/resource/?sort=2') as resp:
        assert resp.status == 200
        assert await resp.json()

    async with client.post('/resource') as resp:
        assert resp.status == 405


async def test_api(aiohttp_client):
    app = muffin.Application('api_test')
    api = mr.Api('/api/v1')
    assert api.prefix == '/api/v1'
    assert api.prefix_name == 'api.v1'

    @api.register
    class Resource(mr.RESTHandler):
        methods = 'get',

    @Resource.register('/action')
    def resource_action(hander, request, resource=None):
        return 'ACTION'

    @Resource.register('/action2', methods=['POST'])
    def resource_post_action(hander, request, resource=None):
        return 'POST ACTION'

    @api.register('/cfg')
    def cfg(request, **kwargs):
        return {'VAR': 'VALUE'}

    assert 'resource' in api.app.router

    api.bind(app)
    assert api.parent is app

    client = await aiohttp_client(app)
    async with client.get('/api/v1/unknown') as resp:
        assert resp.status == 404

    async with client.get('/api/v1/cfg') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json

    async with client.get('/api/v1/resource') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json == []

    async with client.get('/api/v1/action') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json == 'ACTION'

    async with client.post('/api/v1/action2') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json == 'POST ACTION'

    async with client.get('/api/v1/action2') as resp:
        assert resp.status == 405

    # Swagger
    async with client.get('/api/v1/') as resp:
        assert resp.status == 200

    async with client.get('/api/v1/schema.json') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json


async def test_peewee(aiohttp_client):
    import muffin_peewee as mpw

    app = muffin.Application('peewee')
    db = app.install(mpw.Plugin, connection="sqlite:///:memory:")

    import peewee as pw
    from muffin_peewee.fields import JSONField

    @db.register
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
            schema = dict(
                id=ma.fields.String(dump_only=True),
                created=Timestamp(),
            )
            filters = 'active', 'name', ('oid', 'id'),

    @ResourceHandler.register('/resource/action')
    def action(handler, request, resource=None):
        return list(handler.collection)

    assert ResourceHandler.Schema
    assert ResourceHandler.name == 'resource'
    assert 'api.resource' in app.router

    client = await aiohttp_client(app)
    async with client.get('/resource') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json == []

    Resource(name='test').save()

    async with client.get('/resource') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json

    async with client.get('/resource/1') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json['id'] == '1'
        assert json['name'] == 'test'

    async with client.get('/resource/action?custom=123') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json

    async with client.post('/resource', json={'active': True}) as resp:
        assert resp.status == 400
        json = await resp.json()
        assert json['errors']
        assert 'name' in json['errors']

    async with client.post('/resource', data={
            'name': 'test2', 'created': 1000000, 'active': True}) as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json['id'] == '2'
        assert json['name'] == 'test2'
        assert json['active']
        created = dt.datetime.fromtimestamp(json['created'])
        assert created.year == 1970

    async with client.patch('/resource/2', json={'name': 'new'}) as resp:
        assert resp.status == 200
        json = await resp.json()
        assert json['id'] == '2'
        assert json['name'] == 'new'
        assert json['active']
        created = dt.datetime.fromtimestamp(json['created'])
        assert created.year == 1970

    async with client.delete('/resource/2') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert not json

    assert Resource.select().where(Resource.id == 1).exists()
    assert not Resource.select().where(Resource.id == 2).exists()

    Resource(name='test2').save()
    Resource(name='test3').save()
    Resource(name='test4').save()

    async with client.get('/resource?where={"name":"test"}') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert len(json) == 1

    async with client.get('/resource?where={"name": {"$in": ["test", "test2"]}}') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert len(json) == 2

    async with client.get('/resource?where={"name": {"$starts": "test"}}') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert len(json) == 4

    async with client.get('/resource?where={"name": {"$ends": "3"}}') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert len(json) == 1

    async with client.get('/resource?where={"name": {"$regexp": "(3|4)"}}') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert len(json) == 2

    async with client.get('/resource?where={"oid": {"$between": ["2", "4"]}}') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert len(json) == 3

    async with client.get('/resource?where={"oid": {"$gt": "2"}}') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert len(json) == 2

    for n in range(6):
        Resource(name='test%d' % n).save()

    async with client.get('/resource') as resp:
        assert resp.status == 200
        json = await resp.json()
        assert len(json) == 10

    async with client.get('/resource?per_page=3') as resp:
        assert resp.status == 200
        assert resp.headers['x-page'] == '0'
        assert resp.headers['x-page-last'] == '3'
        assert resp.headers['x-total-count'] == '10'
        json = await resp.json()
        assert len(json) == 3

#  pylama:ignore=W0621,W0612
