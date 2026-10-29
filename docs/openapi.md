# OpenAPI

The spec is generated from the router, the handlers, and their docstrings. There
is no separate schema file to keep in sync.

## Endpoints

`api.setup()` mounts three routes under the API prefix:

- `/api/swagger` for Swagger UI
- `/api/redoc` for ReDoc
- `/api/openapi.json` for the spec

Disable them per API or per setup call:

```python
api = API(openapi=False)
api.setup(app, prefix="/api", openapi=False)
```

Info fields and servers are passed to `API` or `setup`:

```python
api = API(
    title="Pet Store",
    version="2.0",
    description="Pets and categories",
    servers=[{"url": "https://example.com/api"}],
)
```

Without `servers`, the spec uses the URL of the request that fetched it.

## What is generated

Every route bound to the API router becomes a path. Handler routes get:

- a tag named `Meta.name`, with the handler class docstring as its description
- a component schema named `{Meta.name.title()}Schema`
- query parameters for `sort`, `where`, `limit`, and `offset` when enabled
- request bodies for `post`, `put`, and collection `delete`
- `200` responses with the resource schema

Plain function routes get their summary, description, responses, and YAML from
the docstring. The HTTP methods come from the `methods` argument, or from the
YAML block when the route accepts any method.

Handler names must be unique. The component name is derived from `Meta.name`, so
two handlers with the same name share the first schema that was registered.

## Docstrings

The first paragraph is the summary. The rest before `---` is the description.
Everything after `---` is YAML merged into the operation:

```python
@api.route("/upload", methods="post")
async def upload(request):
    """Upload a file.

    The file is stored on disk.

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
    ...
```

The same works on handler methods:

```python
class Pets(PWRESTHandler):
    class Meta:
        model = Pet

    @PWRESTHandler.route("/pet/{id}/image", methods="post")
    async def upload_image(self, request, *, resource: Pet):
        """Upload a pet image.

        ---
        requestBody:
            content:
                multipart/form-data:
                    schema:
                        type: object
                        properties:
                            file: {type: string, format: binary}
        """
        ...
```

YAML parsing requires PyYAML. Install `muffin-rest[yaml]` or add `pyyaml`
yourself. Without it, docstring summaries and YAML blocks are not parsed; the
spec falls back to the generated defaults.

## Authorization

The docstring of the `@api.authorization` callback becomes the security scheme.
Each top-level key is a scheme name:

```python
@api.authorization
async def authorize(request):
    """Check the request.

    ---
    bearerAuth:
        type: http
        scheme: bearer
    """
    return request.headers.get("authorization", "")
```

This registers `bearerAuth` and applies it globally. To mark one operation as
anonymous, set `security` to an empty list in its YAML:

```python
@api.route("/token", methods="get")
async def token(request):
    """Get a token.

    ---
    get:
        security: []
    """
    ...
```

## Responses

If a method's return annotation is a Muffin `Response` subclass with a content
type, the spec uses its status code and content type:

```python
from muffin import ResponseText

@api.route("/token", methods="get")
async def token(request) -> ResponseText:
    """Get a token."""
    return ResponseText("...")
```

Without an annotation, handler methods get a `200` response with the resource
schema, or an array of resources for list requests. Delete operations get a
`200` with no body. Peewee still returns the deleted ids at runtime, so add a
body to the YAML if clients rely on them. Override any of this with YAML:

```python
"""Delete a pet.

---
responses:
    404:
        description: Pet not found
"""
```

## Caching

The spec is built once per route set and cached. The cache key is the list of
route paths and methods. Changing `Meta.filters`, `Meta.sorting`, `Meta.Schema`,
or a docstring after the first spec request does not rebuild the spec until the
route is registered again or the process restarts.

This matters for tests and for applications that modify handlers at runtime.
Register routes before serving the first spec request.

## Programmatic access

`render_openapi(api, request=None)` returns the spec as a dictionary:

```python
from muffin_rest.openapi import render_openapi

spec = render_openapi(api)
```

Pass a request to include the request-derived `servers` entry.
