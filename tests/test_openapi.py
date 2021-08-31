import marshmallow as ma


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


    @api.route('/cats', '/cats/{cat}')
    class Cat(RESTHandler):

        methods = 'get', 'post'

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
