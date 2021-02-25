from muffin_rest import API, __version__
from muffin_rest.peewee import PeeweeEndpoint
import string
import random
from muffin import ResponseText

from example.models import Pet


api = API(apispec_params={
    'version': __version__,
    'info': {
        'title': 'PetStore API',
        'description': 'Example Petstore API',
    }
})


@api.authorization
async def authorization(request):
    """Setup authorization for whole API.

    Can be redefined for an endpoint.

    ---
    # OpenAPI Authorization Specs

    Auth:
        type: http
        scheme: bearer
    """
    # Decode tokens, load/check users and etc
    # ...
    # in the example we just ensure that the authorization header exists
    return request.headers.get('authorization', '')


@api.route('/token')
async def token(request) -> ResponseText:
    """A simple endpoint to get current API token.

    By default authorization is only awailable for class based endpoints.
    So the endpoint supports anonimous access.

    If you would like to use API authorization for the simple endpoints, you have to
    call it explicitly:

        res = await api.auth(request)
        if not res:
            ...

    ---
    # OpenAPI Specs

    # Mark the method as anonymous
    get:
        security: []

    """
    return ResponseText(''.join(random.choices(string.ascii_uppercase + string.digits, k=42)))


@api.route
class Pets(PeeweeEndpoint):
    """Everything about your Pets."""

    class Meta:
        model = Pet
        limit = 10
        sorting = 'id', 'name'
        filters = 'status', 'category'
