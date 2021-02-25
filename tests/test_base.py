import pytest
import marshmallow as ma


@pytest.fixture
def api(app):
    from muffin_rest import API

    api = API(app, prefix='/api')

    @api.authorization
    async def fake_auth(request):
        return not request.url.query.get('guest')

    return api


async def test_conf(client):
    res = await client.get('/')
    assert res.status_code == 200
    assert await res.text() == 'OK'


async def test_api(app, client):
    from muffin_rest import API

    api = API()
    assert api

    api.setup(app, prefix='/api')
    assert api.app
    assert api.prefix == '/api'

    res = await client.get('/api')
    assert res.status_code == 404

    @api.route('/simple')
    async def simple_endpoint(request):
        return {'data': 'simple'}

    res = await client.get('/api/simple')
    assert res.status_code == 200
    assert await res.json() == {'data': 'simple'}


async def test_endpoints(api, client):

    from muffin_rest import Endpoint

    assert Endpoint

    class FakeSchema(ma.Schema):

        def dump(self, data, **kwargs):
            return data

        def load(self, data, **kwargs):
            return data

    @api.route('/simple')
    class Simple(Endpoint):

        methods = 'get', 'put'

        class Meta:
            Schema = FakeSchema

        async def prepare_collection(self, request):
            return f'SIMPLE {request.method}'

    assert Simple.meta
    assert Simple.meta.name == 'simple'
    assert Simple.meta.limit == 0
    assert Simple.meta.filters
    assert Simple.meta.sorting == {}
    assert Simple.methods == {'GET', 'PUT'}
    assert api.router.routes()[1].methods == Simple.methods

    res = await client.get('/api/simple')
    assert res.status_code == 200
    assert await res.body() == b'SIMPLE GET'

    res = await client.put('/api/simple')
    assert res.status_code == 404
    assert await res.json() == {'error': True, 'message': 'Nothing matches the given URI'}

    res = await client.post('/api/simple')
    assert res.status_code == 405

    res = await client.get('/api/simple?guest=1')
    assert res.status_code == 401
    assert await res.json() == {
        'error': True, 'message': 'No permission -- see authorization schemes'}

    @api.route('/simple2')
    class Simple2(Endpoint):

        class Meta:
            sorting = 'test',
            Schema = FakeSchema

    assert Simple2.methods == {'POST', 'PUT', 'GET', 'DELETE'}
    assert Simple2.meta.sorting == {'test': True}

    source = [1, 2, 3]

    @api.route
    class Source(Endpoint):

        class Meta:
            filters = 'val',
            limit = 10
            Schema = FakeSchema

        async def prepare_collection(self, request):
            return source

        async def paginate(self, request, limit, offset):
            return self.collection[offset: offset + limit], len(source)

        async def load(self, request, resource=None):
            data = await super().load(request, resource=resource)
            if resource:
                source[int(resource)] = data
            return data

        async def save(self, request, resource=None):
            if resource not in source:
                source.append(resource)
            return resource

        async def remove(self, request, resource=None):
            source.remove(source[int(resource)])

        @Endpoint.route('/source/custom', methods='get')
        async def custom(self, request, resource=None):
            return 'source: custom'

    assert Source.meta.filters
    assert Source.meta.filters.filters

    # Get collection
    res = await client.get('/api/source')
    assert res.status_code == 200
    assert await res.json() == source

    # Create a resource
    res = await client.post('/api/source', json=42)
    assert res.status_code == 200
    assert await res.json() == 42

    # Update a resource
    res = await client.put('/api/source/3', json=99)
    assert res.status_code == 200
    assert await res.json() == 99
    assert source == [1, 2, 3, 99]

    # Delete a resource
    res = await client.delete('/api/source/3')
    assert res.status_code == 200
    assert source == [1, 2, 3]

    # Filter results
    res = await client.get('/api/source?where={"val": 2}')
    assert res.status_code == 200
    assert await res.json() == [2]

    # Filter results
    res = await client.get('/api/source?where={"val": {">=": 2}}')
    assert res.status_code == 200
    assert await res.json() == [2, 3]

    # Paginate results
    res = await client.get('/api/source?limit=2')
    assert res.status_code == 200
    assert res.headers['x-total'] == str(len(source))
    assert res.headers['x-limit'] == '2'
    assert res.headers['x-offset'] == '0'
    assert await res.json() == [1, 2]

    res = await client.get('/api/source?limit=2&offset=1')
    assert res.status_code == 200
    assert await res.json() == [2, 3]

    res = await client.get('/api/source/custom')
    assert res.status_code == 200
    assert await res.text() == 'source: custom'

    res = await client.post('/api/source/custom')
    assert res.status_code == 405


async def test_endpoints_with_schema(api, client):
    from muffin_rest import Endpoint

    pets = []

    @api.route('/pets', '/pets/{pet}')
    class Pet(Endpoint):

        methods = 'get', 'post'

        class Meta:

            class Schema(ma.Schema):
                name = ma.fields.String(required=True)

        async def prepare_collection(self, request):
            return pets

        async def save(self, request, resource):
            pets.append(resource)
            return resource

    res = await client.post('/api/pets', json={})
    assert res.status_code == 400
    json = await res.json()
    assert json
    assert json['errors']

    res = await client.post('/api/pets', json={'name': 'muffin'})
    assert res.status_code == 200
    json = await res.json()
    assert json == {'name': 'muffin'}

    res = await client.get('/api/pets')
    assert res.status_code == 200
    json = await res.json()
    assert json == [{'name': 'muffin'}]


async def test_apispec(api, client):
    from muffin_rest import Endpoint

    @api.authorization
    async def authorization(request):
        """Setup authorization for whole API.

        Can be redefined for an endpoint.

        ---

        bearerAuth:
            type: http
            scheme: bearer


        """
        # Decode tokens, load/check users and etc
        # ...
        # in the example we just ensure that the authorization header exists
        return request.headers.get('authorization', '')

    @api.route('/token', methods='get')
    async def token(request) -> str:
        """Get user token."""
        return 'TOKEN'

    @api.route('/pets', '/pets/{pet}')
    class Pet(Endpoint):

        methods = 'get', 'post'

        class Meta:

            class Schema(ma.Schema):
                name = ma.fields.String(required=True)

    async with client.lifespan():

        res = await client.get('/api/swagger')
        assert res.status_code == 200
        assert 'swagger' in await res.text()

        res = await client.get('/api/openapi.json')
        assert res.status_code == 200
        spec = await res.json()
        assert spec
        assert spec['paths']
        assert spec['paths']['/token']
        assert spec['paths']['/token']['get']
        assert spec['paths']['/token']['get']['responses']