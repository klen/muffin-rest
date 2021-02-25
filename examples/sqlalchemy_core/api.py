import random
import string

from muffin import ResponseText
from muffin_rest import API, __version__
from muffin_rest.sqlalchemy import SAEndpoint

from . import db
from .tables import Pet


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
        description: Use any value
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
class Pets(SAEndpoint):
    """Everything about your Pets."""

    class Meta:

        # ORM table
        table = Pet
        database = db

        # Pagination
        limit = 10

        # Avalable sort params
        sorting = 'id', 'name'

        # Available filters
        filters = 'status', 'category'
