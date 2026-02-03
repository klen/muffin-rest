import marshmallow as ma
import pytest


@pytest.fixture(autouse=True)
def _setup(api):
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
        return request.headers.get("authorization", "")

    @api.route("/token", methods="get")
    async def token(request) -> str:
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
