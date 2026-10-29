# Tutorial: a pet store API

This walkthrough builds a small API with the Peewee backend. The same handler
shape works for SQLAlchemy and Mongo; only `Meta` changes.

## 1. Install

```bash
pip install "muffin-rest[peewee]" uvicorn aiosqlite
```

`aiosqlite` is the driver for the SQLite file used here. In production you
would use the driver for your database instead.

## 2. Define the application and model

Create `app.py`:

```python
import peewee as pw
from muffin import Application
from muffin_peewee import Plugin as Peewee
from muffin_rest import API
from muffin_rest.peewee import PWRESTHandler

app = Application("petstore", debug=True)
db = Peewee(app, connection="aiosqlite:///./petstore.db")


class Pet(db.Model):
    name = pw.CharField()
    status = pw.CharField(default="available")


@app.on_startup
async def create_tables():
    await db.create_tables(Pet)


api = API(title="Pet Store", version="1.0")


@api.route
class Pets(PWRESTHandler):
    class Meta:
        model = Pet
        filters = ("status", "name")
        sorting = ("name", ("id", {"default": "desc"}))
        limit = 10


api.setup(app, prefix="/api")
```

Three things happen here:

- `db.Model` is a `peewee_aio` model bound to the plugin's manager.
- `Pets.Meta.model` tells the handler what to read and write.
- `api.route` without a path creates `/pet` and `/pet/{id}` from `Meta.name`,
  which defaults to the table name.

## 3. Run it

```bash
uvicorn app:app --reload
```

Open `http://localhost:8000/api/swagger`. The spec is generated from the
handler, so the routes already show up. OpenAPI is covered in
[OpenAPI](openapi.md).

## 4. Create and read

```bash
curl -X POST http://localhost:8000/api/pet \
  -H 'content-type: application/json' \
  -d '{"name": "Muffin"}'

curl http://localhost:8000/api/pet
curl http://localhost:8000/api/pet/1
```

A create returns the stored resource with its generated id. A list request
returns an array and sets `x-limit`, `x-offset`, and `x-total` headers.

## 5. Filter, sort, and paginate

```bash
curl -g 'http://localhost:8000/api/pet?where={"status":"available"}'
curl 'http://localhost:8000/api/pet?sort=-id'
curl 'http://localhost:8000/api/pet?limit=5&offset=10'
```

Only fields declared in `Meta.filters` and `Meta.sorting` are accepted.
Unknown fields are ignored instead of failing the request. The full syntax is
in [Querying](querying.md).

## 6. Update and delete

```bash
curl -X PUT http://localhost:8000/api/pet/1 \
  -H 'content-type: application/json' \
  -d '{"status": "sold"}'

curl -X DELETE http://localhost:8000/api/pet/1
```

`PUT` is a partial update: fields missing from the body keep their current
values. `DELETE` on the collection endpoint accepts a JSON array of ids:

```bash
curl -X DELETE http://localhost:8000/api/pet \
  -H 'content-type: application/json' \
  -d '["1", "2"]'
```

## 7. Add authorization

Authorization is set once on the API:

```python
@api.authorization
async def authorize(request):
    return request.headers.get("authorization", "")
```

Every handler now returns `401` unless the callback returns a truthy value.
The callback result is available as `self.auth` inside handlers. To vary the
rules per resource, override `authorize` on the handler and call `super()`.
See [Cookbook](cookbook.md#authorization-and-rate-limiting).

## 8. Add a custom action

Methods decorated with `@PWRESTHandler.route` are bound next to the generated
routes. They still receive the loaded `resource` when the path contains `{id}`:

```python
class Pets(PWRESTHandler):
    class Meta:
        model = Pet

    @PWRESTHandler.route("/pet/{id}/adopt", methods="post")
    async def adopt(self, request, *, resource: Pet):
        """Mark a pet as adopted."""
        resource.status = "sold"
        await resource.save()
        return await self.dump(request, resource)
```

`POST /api/pet/1/adopt` loads the pet, changes it, and returns the serialized
result. The docstring of the method becomes the OpenAPI description.

## 9. Where to go next

- [Handlers and lifecycle](handlers.md) explains the order of hooks and how to
  replace loading, saving, or pagination.
- [Backends](backends.md) covers SQLAlchemy Core and Mongo.
- [Schemas](schemas.md) covers validation and custom fields.
