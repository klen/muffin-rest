# Cookbook

Short recipes for changes that are common but not part of the core API.

## Authorization and rate limiting

`@api.authorization` sets one callback for every handler:

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

Handlers call it through `self.authorize`. Override that to add per-resource
rules and call `super()` to keep the API callback:

```python
from muffin_rest import APIError
from muffin_rest.limits import MemoryRateLimiter

limiter = MemoryRateLimiter(60, period=60)

class Pets(PWRESTHandler):
    async def authorize(self, request):
        if not await limiter.check(request.client[0]):
            raise APIError.TOO_MANY_REQUESTS("Rate limit exceeded")
        return await super().authorize(request)
```

`MemoryRateLimiter` stores counters in the process. It is fine for a single
worker and for tests. For multiple workers use `RedisRateLimiter`:

```python
from muffin_rest.limits import RedisRateLimiter

limiter = RedisRateLimiter(60, period=60, redis=redis)
```

The limiter is keyed by whatever string you pass. Use a user id or an API key
when you have one; the client address is only a fallback.

## Scope every query to the current user

Override `prepare_collection` and use `self.auth`:

```python
class Orders(PWRESTHandler):
    class Meta:
        model = Order

    async def prepare_collection(self, request):
        return super().prepare_collection(request).where(Order.user_id == self.auth)
```

The same works for SQLAlchemy:

```python
return super().prepare_collection(request).where(order_table.c.user_id == self.auth)
```

For Mongo, `prepare_collection` returns a `MongoChain`:

```python
async def prepare_collection(self, request):
    return super().prepare_collection(request).find({"user_id": self.auth})
```

A detail request loads the resource through the same collection, so a row
belonging to another user returns `404`.

## Soft delete

Keep the rows, hide them from queries, and turn delete into an update:

```python
import datetime as dt

class Pets(PWRESTHandler):
    class Meta:
        model = Pet

    async def prepare_collection(self, request):
        return super().prepare_collection(request).where(Pet.deleted_at.is_null())

    async def remove(self, request, resource=None):
        if resource is not None:
            resources = [resource]
        else:
            ids = await request.data()
            if not ids:
                raise APIError.NOT_FOUND()
            resources = await self.meta.manager.fetchall(
                self.collection.where(self.meta.model_pk << ids)
            )

        if not resources:
            raise APIError.NOT_FOUND()

        for item in resources:
            item.deleted_at = dt.datetime.now(dt.UTC)
            await item.save()

        return resource.get_id() if resource else [item.get_id() for item in resources]
```

`PWRESTHandler.delete` calls `remove`, so this covers both detail and batch
deletes. For SQLAlchemy and Mongo, override `delete` instead; see the note in
[Handlers and lifecycle](handlers.md#overriding-crud).

## Custom filter

Use a backend filter class when the query language has the operator:

```python
from muffin_rest.peewee.filters import PWFilter

class ContainsFilter(PWFilter):
    async def filter(self, collection, *ops, **ctx):
        return collection.where(self.field.contains(ops[0][1]))

class Users(PWRESTHandler):
    class Meta:
        model = User
        filters = (ContainsFilter("name"),)
```

The filter name still comes from `Filter.name`, so the request is
`?where={"name": "uf"}`. The operator is ignored because this filter always
uses `contains`. The `schema_field` is taken from the schema field with the same
name, which converts the value to the right type.

## Expose a column under another name

Map the public filter name to the database column:

```python
class Meta:
    model = Order
    filters = (("user", {"field": "user_id"}),)
    sorting = (("user", {"field": "user_id"}),)
```

Now `?where={"user": 42}` and `?sort=-user` work without exposing `user_id`.

## File upload

A custom route can read multipart data and update the loaded resource:

```python
from pathlib import Path

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
    form = await request.form(upload_to=Path("uploads"))
    resource.image = form["file"].name
    await resource.save()
    return resource.image
```

Returning a string is fine; Muffin turns it into a text response. Annotate the
method with `-> ResponseText` if you want the OpenAPI response type to be
`text/plain`.

## Return a different status code

Override the HTTP method and adjust the response:

```python
async def post(self, request, *, resource=None):
    response = await super().post(request, resource=resource)
    if resource is None:
        response.status_code = 201
    return response
```

`resource is None` means a create on the collection route; a `POST` with an id
is an update and stays `200`.

## Batch insert in one transaction

`save_many` loops over `save` by default. Wrap it when a partial batch must not
be visible:

```python
class Pets(PWRESTHandler):
    class Meta:
        model = Pet

    async def save_many(self, request, data, *, update=False):
        async with self.meta.manager.transaction():
            return await super().save_many(request, data, update=update)
```

For SQLAlchemy, use `self.meta.database.database.transaction()` in the same
shape. Check whether your plugin already opens a transaction per request before
adding another one.

## Test a handler

Use `ASGITestClient` and open the lifespan so startup hooks run:

```python
from asgi_tools.tests import ASGITestClient

async def test_list(app):
    client = ASGITestClient(app)
    async with client.lifespan():
        response = await client.get("/api/pet")
        assert response.status_code == 200
        assert await response.json() == []
```

Query parameters with JSON need encoding:

```python
import json

response = await client.get(
    "/api/pet",
    query={"where": json.dumps({"status": "available"})},
)
```

Backend test suites pin the async library to asyncio:

```python
import pytest

@pytest.fixture(scope="module")
def aiolib():
    return "asyncio", {"loop_factory": None}
```

The base suite runs under asyncio, trio, and curio. Backend suites use asyncio
because the database drivers do.
