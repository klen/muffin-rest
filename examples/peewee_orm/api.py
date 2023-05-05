"""Setup API for Peewee ORM models."""

import random
import string
from pathlib import Path

from muffin import ResponseText

from muffin_rest import API
from muffin_rest.peewee import PWRESTHandler

from .models import Pet
from .schemas import PetSchema

api = API(version="0.0.0", title="PetStore API", description="Example Petstore API")


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
    return request.headers.get("authorization", "")


@api.route("/token")
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
    return ResponseText(
        "".join(random.choices(string.ascii_uppercase + string.digits, k=42))
    )


@api.route
class Pets(PWRESTHandler):
    """Everything about your Pets."""

    class Meta:
        """Tune the endpoint."""

        # ORM Model
        model = Pet

        # Schema for serialization (it can be created automatically)
        Schema = PetSchema

        # Pagination
        limit = 10

        # Avalable sort params
        sorting = ("id", {"default": "desc"}), "name"

        # Available filters
        filters = "status", "category"

    @PWRESTHandler.route("/pet/{id}/uploadImage", methods="post")
    async def upload_image(self, request, resource=None):
        """Uploads an image.

        ---

        requestBody:
            required: true
            content:
                multipart/form-data:
                    schema:
                        type: object
                        properties:
                            file:
                                type: string
                                format: binary

        """
        formdata = await request.form(upload_to=Path(__file__).parent)
        resource.image = formdata["file"].name
        resource.save()
        return resource.image
