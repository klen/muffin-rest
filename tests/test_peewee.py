import peewee as pw
from muffin_peewee import Plugin as Peewee, JSONField


async def test_base(app, client):
    from muffin_rest import API
    from muffin_rest.peewee import PeeweeEndpoint

    db = Peewee(app, connection='sqlite:///:memory:')
    api = API(app, '/api')

    @db.register
    class Resource(pw.Model):
        active = pw.BooleanField(default=False)
        name = pw.CharField(null=False)
        count = pw.IntegerField(null=True)
        config = JSONField(default={})

    await db.conftest()

    @api.route
    class ResourceEndpoint(PeeweeEndpoint):

        class Meta:
            filters = 'active', 'name', ('oid', 'id'),
            limit = 10
            model = Resource
            sorting = 'name', Resource.count

        @PeeweeEndpoint.route('/resource/action')
        async def action(self, request, resource=None):
            return await self.dump(request, list(self.collection))

    assert ResourceEndpoint
    assert ResourceEndpoint.meta.name == 'resource'
    assert ResourceEndpoint.meta.Schema

    assert api.router.plain['/resource']
    assert api.router.dynamic[0].pattern.pattern == '/resource/(?P<resource>[^/]+)$'

    res = await client.get('/api/resource')
    assert res.status_code == 200
    assert await res.json() == []

    Resource(name='test').save()

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

    res = await client.get('/api/resource/action?custom=123')
    assert res.status_code == 200
    json = await res.json()
    assert json

    res = await client.post('/api/resource', json={'active': True})
    assert res.status_code == 400
    json = await res.json()
    assert json['errors']
    assert 'name' in json['errors']

    res = await client.post('/api/resource', data={'name': 'test2', 'active': True})
    assert res.status_code == 200
    json = await res.json()
    assert json['id'] == '2'
    assert json['name'] == 'test2'
    assert json['active']

    res = await client.patch('/api/resource/2', data={'name': 'new'})
    assert res.status_code == 200
    json = await res.json()
    assert json['name'] == 'new'
    assert json['id'] == '2'

    res = await client.delete('/api/resource/2')
    assert res.status_code == 200
    json = await res.json()
    assert not json

    assert Resource.select().where(Resource.id == 1).exists()
    assert not Resource.select().where(Resource.id == 2).exists()

    Resource(name='test2', count=2).save()
    Resource(name='test3', count=3).save()
    Resource(name='test4', count=1).save()

    res = await client.get('/api/resource?sort=-count')
    assert res.status_code == 200
    json = await res.json()
    assert json[0]['id'] == '3'
    assert json[1]['id'] == '2'

    res = await client.get('/api/resource?where={"name":"test"}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 1

    res = await client.get('/api/resource?where={"name": {"$in": ["test", "test2"]}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 2

    res = await client.get('/api/resource?where={"name": {"$starts": "test"}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 4

    res = await client.get('/api/resource?where={"name": {"$ends": "3"}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 1

    res = await client.get('/api/resource?where={"oid": {"$between": ["2", "4"]}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 3

    res = await client.get('/api/resource?where={"oid": {"$gt": "2"}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 2

    for n in range(6):
        Resource(name='test%d' % n).save()

    res = await client.get('/api/resource')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 10

    res = await client.get('/api/resource?limit=3')
    assert res.status_code == 200
    assert res.headers['x-total'] == '10'
    assert res.headers['x-limit'] == '3'
    assert res.headers['x-offset'] == '0'
    json = await res.json()
    assert len(json) == 3

    res = await client.get('/api/resource?limit=3&offset=4')
    assert res.status_code == 200
    assert res.headers['x-total'] == '10'
    assert res.headers['x-limit'] == '3'
    assert res.headers['x-offset'] == '4'
    json = await res.json()
    assert len(json) == 3

    # Batch operations (only POST/DELETE are supported for now)
    res = await client.post('/api/resource', json=[
        {'name': 'test3', 'active': True},
        {'name': 'test4', 'active': True},
        {'name': 'test6', 'active': True},
    ])
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 3
    assert json[0]['id'] == '11'
    assert json[1]['id'] == '12'
    assert json[2]['id'] == '13'

    res = await client.delete('/api/resource', json=['11', '12', '13'])
    assert res.status_code == 200

    assert not Resource.select().where(Resource.id << ('11', '12', '13')).count()
