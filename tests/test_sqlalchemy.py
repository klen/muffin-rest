import pytest
import sqlalchemy as sa
from muffin_databases import Plugin as DB


@pytest.mark.parametrize('aiolib', ['asyncio'])
async def test_base(app, client):
    from muffin_rest import API
    from muffin_rest.sqlalchemy import SARESTHandler

    db = DB(app, url='sqlite:///:memory:', params={'force_rollback': True})
    api = API(app, '/api')

    await db.connect()

    meta = sa.MetaData()
    Resource = sa.Table(
        'resource', meta,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('active', sa.Boolean, default=False, nullable=False),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('count', sa.Integer),
    )

    await db.execute(
        'create table resource ('
        'id integer primary key,'
        'active integer default 0,'
        'name varchar(256) not null,'
        'count integer)'
    )

    @api.route
    class ResourceEndpoint(SARESTHandler):

        class Meta:
            database = db
            filters = 'active', 'name', ('oid', 'id'),
            limit = 10
            sorting = 'name', 'count'
            table = Resource

        @SARESTHandler.route('/resource/action')
        async def action(self, request, resource=None):
            rows = await self.meta.database.fetch_all(self.collection)
            return await self.dump(request, rows)

    assert ResourceEndpoint
    assert ResourceEndpoint.meta.name == 'resource'
    assert ResourceEndpoint.meta.Schema
    assert ResourceEndpoint.meta.Schema.opts.dump_only == ('id',)

    assert api.router.plain['/resource']
    assert api.router.dynamic[0].pattern.pattern == '^/resource/(?P<id>[^/]+)$'

    res = await client.get('/api/resource')
    assert res.status_code == 200
    assert await res.json() == []

    await db.execute(Resource.insert(), values={'name': 'test'})
    res = await client.get('/api/resource')
    assert res.status_code == 200
    json = await res.json()
    assert json[0]['id'] == 1
    assert json[0]['count'] is None
    assert json[0]['name'] == 'test'

    res = await client.get('/api/resource/1')
    assert res.status_code == 200
    assert await res.json() == {
        'active': None,
        'count': None,
        'id': 1,
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
    assert json['id'] == 2
    assert json['name'] == 'test2'
    assert json['active']

    res = await client.put('/api/resource/2', data={'name': 'new'})
    assert res.status_code == 200
    json = await res.json()
    assert json['name'] == 'new'
    assert json['id'] == 2

    res = await client.delete('/api/resource/2')
    assert res.status_code == 200
    json = await res.json()
    assert not json

    assert await db.fetch_one(Resource.select().where(Resource.c.id == 1))
    assert not await db.fetch_one(Resource.select().where(Resource.c.id == 2))

    await db.execute_many(Resource.insert(), [
        {'name': 'test2', 'count': 2},
        {'name': 'test3', 'count': 3},
        {'name': 'test4', 'count': 1},
    ])

    res = await client.get('/api/resource?sort=-count')
    assert res.status_code == 200
    json = await res.json()
    assert json[0]['id'] == 3
    assert json[1]['id'] == 2

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

    res = await client.get('/api/resource?where={"oid": {"$between": [2, 4]}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 3

    res = await client.get('/api/resource?where={"oid": {"$gt": "2"}}')
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 2

    await db.execute_many(Resource.insert(), [
        {'name': 'test%d' % n} for n in range(6)
    ])

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
    assert json[0]['id'] == 11
    assert json[1]['id'] == 12
    assert json[2]['id'] == 13

    res = await client.delete('/api/resource', json=[11, 12, 13])
    assert res.status_code == 200

    assert not await db.fetch_all(Resource.select().where(Resource.c.id.in_([11, 12, 13])))

    # Test openapi
    res = await client.get('/api/openapi.json')
    assert res.status_code == 200
    json = await res.json()
    assert json

    await db.disconnect()
