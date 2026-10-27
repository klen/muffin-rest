import marshmallow as ma
import pytest
from asgi_tools.request import Request


@pytest.fixture(autouse=True)
def _setup(api):
    from muffin_rest import RESTHandler

    @api.authorization
    async def authorization(request: Request):
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
        return request.headers.get("authorization", "")

    @api.route("/token", methods="get")
    async def token(request: Request) -> str:
        """Get user token."""
        return "TOKEN"

    @api.route("/pets", "/pets/{id}")
    class Pet(RESTHandler):
        methods = "get", "post"

        class Meta:
            name = "pet"
            sorting = ("name",)

            class Schema(ma.Schema):
                name = ma.fields.String(required=True)

        async def get(self, request: Request, *, resource=None):
            """Get pets list or pet by id."""
            return await super().get(request, resource=resource)

    @api.route("/cats", "/cats/{id}")
    class Cat(RESTHandler):
        methods = "get", "post"


async def test_openapi(api):
    from muffin_rest.openapi import render_openapi

    spec = render_openapi(api)
    assert spec
    assert spec["openapi"]
    assert spec["components"]
    assert spec["paths"]

    paths = spec["paths"]
    assert "/token" in paths
    assert "/pets" in paths

    pets = paths["/pets"]
    assert "get" in pets
    assert "responses" in pets["get"]
    # assert pets["get"]["responses"]  # noqa: ERA001


async def test_apispec(api, client):
    async with client.lifespan():
        res = await client.get("/api/swagger")
        assert res.status_code == 200
        assert "swagger" in await res.text()

        res = await client.get("/api/openapi.json")
        assert res.status_code == 200
        spec = await res.json()
        assert spec
        assert spec["openapi"]
        assert spec["info"]
        assert spec["paths"]
        assert spec["paths"]["/token"]
        assert spec["paths"]["/token"]["get"]
        assert spec["paths"]["/token"]["get"]["responses"]
        assert spec["paths"]["/pets"]["get"]["parameters"]
        assert spec["paths"]["/pets"]["get"]["parameters"][0]["name"] == "sort"


def _handler_api():
    from muffin_rest import API

    return API(title="Demo", version="1.0")


def test_schema_components_are_unique():
    from muffin_rest import RESTHandler
    from muffin_rest.openapi import render_openapi

    api = _handler_api()

    @api.route
    class Pets(RESTHandler):
        class Meta:
            name = "pet"

            class Schema(ma.Schema):
                name = ma.fields.String()

        async def prepare_collection(self, request):
            return []

    @api.route
    class Cats(RESTHandler):
        class Meta:
            name = "cat"

            class Schema(ma.Schema):
                name = ma.fields.String()

        async def prepare_collection(self, request):
            return []

    spec = render_openapi(api)
    assert "PetSchema" in spec["components"]["schemas"]
    assert "CatSchema" in spec["components"]["schemas"]

    pet = spec["paths"]["/pet"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    cat = spec["paths"]["/cat"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert pet["items"] == {"$ref": "#/components/schemas/PetSchema"}
    assert cat["items"] == {"$ref": "#/components/schemas/CatSchema"}


def test_responses_and_request_bodies():
    from muffin_rest import RESTHandler
    from muffin_rest.openapi import render_openapi

    api = _handler_api()

    @api.route
    class Pets(RESTHandler):
        class Meta:
            name = "pet"
            limit = 10
            sorting = ("name",)

            class Schema(ma.Schema):
                name = ma.fields.String()

        async def prepare_collection(self, request):
            return []

    spec = render_openapi(api)
    paths = spec["paths"]

    get_schema = paths["/pet"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert get_schema == {"type": "array", "items": {"$ref": "#/components/schemas/PetSchema"}}

    assert paths["/pet"]["get"]["parameters"][0]["schema"]["items"]["enum"] == ["name", "-name"]

    post_schema = paths["/pet"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert post_schema["oneOf"][0] == {"$ref": "#/components/schemas/PetSchema"}
    assert post_schema["oneOf"][1] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/PetSchema"},
    }

    delete_body = paths["/pet"]["delete"]["requestBody"]["content"]["application/json"]["schema"]
    assert delete_body == {"type": "array", "items": {"type": "string"}}

    assert paths["/pet/{id}"]["parameters"] == [
        {"in": "path", "name": "id", "required": True, "schema": {"type": "string"}},
    ]


def test_render_does_not_mutate_options():
    from muffin_rest.openapi import render_openapi

    api = _handler_api()
    render_openapi(api)
    render_openapi(api)
    assert api.openapi_options["info"] == {"title": "Demo", "version": "1.0"}


def test_function_methods_from_docstring():
    from muffin_rest.openapi import render_openapi

    api = _handler_api()

    @api.route("/upload")
    async def upload(request):
        """Upload a file.

        ---
        post:
            security: []
        """
        return {"ok": True}

    spec = render_openapi(api)
    assert "post" in spec["paths"]["/upload"]
    assert "get" not in spec["paths"]["/upload"]
