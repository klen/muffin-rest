import pytest
import marshmallow as ma


class FakeSchema(ma.Schema):

    def dump(self, data, **kwargs):
        return data

    def load(self, data, **kwargs):
        return data


@pytest.fixture
def api(app):
    from muffin_rest import API

    api = API(app, prefix='/api', title='API Title')

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


async def test_api_methods(api, client):

    @api.route('/simple')
    async def simple_endpoint(request):
        return {'data': 'simple'}

    res = await client.get('/api/simple')
    assert res.status_code == 200
    assert await res.json() == {'data': 'simple'}


async def test_handler(api, client):
    from muffin_rest import RESTHandler
    from muffin_rest.filters import Filters
    from muffin_rest.sorting import Sorting

    assert RESTHandler

    @api.route('/simple')
    class Simple(RESTHandler):

        methods = 'get', 'put'

        class Meta:
            name = 'simple'
            sorting = 'test',
            schema_base = FakeSchema

        async def prepare_collection(self, request):
            return f'SIMPLE {request.method}'

    assert Simple.meta
    assert Simple.meta.name == 'simple'
    assert Simple.meta.limit == 0
    assert Simple.meta.filters is not None
    assert isinstance(Simple.meta.filters, Filters)
    assert Simple.meta.sorting is not None
    assert isinstance(Simple.meta.sorting, Sorting)
    assert Simple.methods == {'GET', 'PUT'}
    assert api.router.routes()[2].methods == Simple.methods
    assert Simple.meta.Schema
    assert issubclass(Simple.meta.Schema, FakeSchema)
    assert Simple.meta.Schema.opts
    assert Simple.meta.Schema.opts.unknown == 'exclude'

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


async def test_handler2(api, client):
    from muffin_rest import RESTHandler, APIError

    source = [1, 2, 3]

    @api.route
    class Source(RESTHandler):

        class Meta:
            name = 'source'
            filters = 'val',
            limit = 10
            Schema = FakeSchema

        async def prepare_collection(self, request):
            return source

        async def prepare_resource(self, request):
            pk = request['path_params'].get(self.meta.name_id)
            if not pk:
                return

            try:
                return source[int(pk)]
            except IndexError:
                raise APIError.NOT_FOUND('Resource not found')

        async def paginate(self, request, limit, offset):
            return self.collection[offset: offset + limit], len(source)

        async def load(self, request, resource=None):
            data = await super().load(request, resource=resource)
            if resource:
                idx = source.index(resource)
                source[idx] = data
            return data

        async def save(self, request, resource=None):
            if resource not in source:
                source.append(resource)
            return resource

        async def remove(self, request, resource=None):
            source.remove(resource)

        @RESTHandler.route('/source/custom', methods='get')
        async def custom(self, request, resource=None):
            return 'source: custom'

    assert Source.meta.filters
    assert Source.meta.filters.mutations

    # Get collection
    res = await client.get('/api/source')
    assert res.status_code == 200
    assert await res.json() == source

    # Get a resource
    res = await client.get('/api/source/1')
    assert res.status_code == 200
    assert await res.json() == 2

    # Get an unknown resource
    res = await client.get('/api/source/99')
    assert res.status_code == 404
    assert await res.json() == {'error': True, 'message': 'Resource not found'}

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


async def test_bad_request(api, client):
    from muffin_rest import RESTHandler

    @api.route('/simple')
    class Simple(RESTHandler):

        methods = 'get', 'post'

        class Meta:
            name = 'simple'

        async def prepare_collection(self, request):
            return f'SIMPLE {request.method}'

        async def save(self, request, resource=None):
            pass

    res = await client.post(
        '/api/simple', data='invalid', headers={'content-type': 'application/json'})
    assert res.status_code == 400


async def test_handlers_with_schema(api, client):
    from muffin_rest import RESTHandler

    pets = []

    @api.route('/pets', '/pets/{pet}')
    class Pet(RESTHandler):

        methods = 'get', 'post'

        class Meta:
            name = 'pet'

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


async def test_handler_with_path(api, client):
    from muffin_rest import RESTHandler

    @api.route
    class Simple(RESTHandler):

        methods = 'get', 'patch'

        class Meta:
            name = 'simple'

        async def prepare_collection(self, request):
            return [1, 2, 3, 4]

        async def patch(self, request, **kwargs):
            return True

    res = await client.get('/api/simple')
    assert res.status_code == 200

    res = await client.patch('/api/simple')
    assert res.status_code == 200


async def test_apispec(api, client):
    from muffin_rest import RESTHandler

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
    class Pet(RESTHandler):

        methods = 'get', 'post'

        class Meta:
            name = 'pet'
            sorting = 'name',

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
        assert spec['paths']['/pets']['get']['parameters']
        assert spec['paths']['/pets']['get']['parameters'][0]['name'] == 'sort'
