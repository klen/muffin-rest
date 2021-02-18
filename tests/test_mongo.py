import pytest
from muffin_mongo import Plugin as Mongo
import marshmallow as ma
from bson import ObjectId


@pytest.mark.parametrize('anyio_backend', ['asyncio'])
async def test_base(app, client):
    from muffin_rest import API
    from muffin_rest.mongo import MongoEndpoint

    mongo = Mongo(app)
    api = API(app, '/api')

    # Link to a resources collection
    resources = mongo.tests.resources

    # Clean the tests collection
    await resources.drop()

    @api.route
    class ResourceEndpoint(MongoEndpoint):

        class Meta:
            collection = resources
            filters = 'active', 'name', ('oid', '_id'),
            limit = 10
            sorting = 'name', 'count'
            schema_fields = {
                'active': ma.fields.Bool(default=False),
                'name': ma.fields.String(required=True),
                'count': ma.fields.Integer(),
            }

        @MongoEndpoint.route('/resource/action')
        async def action(self, request, resource=None):
            rows = await self.meta.collection.find().to_list(None)
            return await self.dump(request, rows)

    assert ResourceEndpoint
    assert ResourceEndpoint.meta.name == 'resource'
    assert ResourceEndpoint.meta.Schema

    assert api.router.plain['/resource']
    assert api.router.dynamic[0].pattern.pattern == '^/resource/(?P<resource>[^/]+)$'

    res = await client.get('/api/resource')
    assert res.status_code == 200
    assert await res.json() == []

    await resources.insert_one({'name': 'test'})
    res = await client.get('/api/resource')
    assert res.status_code == 200
    json = await res.json()
    assert json[0]['_id']
    assert not json[0]['active']
    assert json[0]['name'] == 'test'

    res = await client.get(f"/api/resource/{ json[0]['_id'] }")
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

    _id = json['_id']

    res = await client.put(f"/api/resource/{ json['_id'] }", data={'name': 'new'})
    assert res.status_code == 200
    json = await res.json()
    assert json['name'] == 'new'
    assert json['_id'] == _id

    res = await client.delete(f"/api/resource/{ _id }")
    assert res.status_code == 200
    json = await res.json()
    assert not json

    assert not await resources.find_one({'_id': _id})
    assert await resources.count_documents({})

    await resources.insert_many([
        {'name': 'test2', 'count': 2},
        {'name': 'test3', 'count': 3},
        {'name': 'test4', 'count': 1},
    ])

    res = await client.get('/api/resource?sort=-count')
    assert res.status_code == 200
    json = await res.json()
    assert json[0]['count'] == 3
    assert json[1]['count'] == 2

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

    _id = json[0]['_id']

    res = await client.get('/api/resource?where={"oid": "%s"}' % _id)
    assert res.status_code == 200
    json = await res.json()
    assert len(json) == 1

    await resources.insert_many([
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
    assert json[0]['_id']
    assert json[1]['_id']
    assert json[2]['_id']

    res = await client.delete('/api/resource', json=[item['_id'] for item in json])
    assert res.status_code == 200

    assert not await resources.find(
        {'_id': {"$in": list(map(ObjectId, [item['_id'] for item in json]))}}).to_list(None)
