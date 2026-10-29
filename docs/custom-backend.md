# Writing a backend

A backend is the part that knows how to talk to one storage system. It does not
implement routing, auth, filters, sorting, pagination headers, validation, or
OpenAPI; `RESTHandler` already does those. A backend supplies five operations:

| Operation | Question it answers |
| --------- | ------------------- |
| `prepare_collection` | what is the base query for this request? |
| `prepare_resource` | which record does `{id}` refer to? |
| `paginate` | how do I take a page and count the total? |
| `save` | how do I create or update a record? |
| `remove` | how do I delete one record or a batch? |

This guide builds a dict-backed backend. Replace the dict operations with calls
to your client; the contract stays the same.

## The complete backend

```python
from uuid import uuid4

from muffin_rest import APIError, RESTHandler
from muffin_rest.options import RESTOptions
from muffin_rest.sorting import Sort, Sorting


class DictSort(Sort):
    async def apply(self, collection, *, desc=False, **ctx):
        field = self.meta.get("field", self.name)
        return sorted(collection, key=lambda obj: obj[field], reverse=desc)


class DictSorting(Sorting):
    MUTATE_CLASS = DictSort

    def sort_default(self, collection):
        for sort in reversed(self.default):
            field = sort.meta.get("field", sort.name)
            collection = sorted(
                collection,
                key=lambda obj: obj[field],
                reverse=sort.meta["default"] == "desc",
            )
        return collection


class DictOptions(RESTOptions):
    base_property = "store"
    sorting_cls = DictSorting
    store: dict[str, dict]


class DictRESTHandler(RESTHandler):
    meta_class = DictOptions

    async def prepare_collection(self, request):
        return list(self.meta.store.values())

    async def prepare_resource(self, request):
        key = request["path_params"].get("id")
        if not key:
            return None

        for item in self.collection:
            if item["id"] == key:
                return item

        raise APIError.NOT_FOUND("Resource not found")

    async def load(self, request, resource=None, **options):
        data = await super().load(request, resource=resource, **options)
        if resource is not None:
            return {**resource, **data}
        return data

    async def paginate(self, request, *, limit=0, offset=0):
        total = len(self.collection) if self.meta.limit_total else None
        return self.collection[offset : offset + limit], total

    async def save(self, request, resource, *, update=False):
        if not update:
            resource["id"] = uuid4().hex
        self.meta.store[resource["id"]] = resource
        return resource

    async def remove(self, request, resource=None):
        if resource is not None:
            self.meta.store.pop(resource["id"], None)
            return resource["id"]

        ids = await request.data()
        if not ids:
            raise APIError.NOT_FOUND()

        for key in ids:
            self.meta.store.pop(key, None)
        return ids
```

Use it like any other handler:

```python
import marshmallow as ma
from muffin import Application
from muffin_rest import API

app = Application("memory")
api = API(app, "/api")
STORE = {}


@api.route
class Items(DictRESTHandler):
    class Meta:
        store = STORE
        schema_fields = {
            "id": ma.fields.String(dump_only=True),
            "name": ma.fields.String(required=True),
            "count": ma.fields.Integer(load_default=0),
        }
        filters = ("name", "count")
        sorting = ("name", ("count", {"default": "desc"}))
        limit = 2
```

`Items` gets `/items` and `/items/{id}`, filtering, sorting, pagination,
validation, and an OpenAPI spec without any more code.

## Options

`meta_class` is where a backend declares what `Meta` means:

```python
class DictOptions(RESTOptions):
    base_property = "store"
    sorting_cls = DictSorting
    store: dict[str, dict]
```

`base_property` names the `Meta` key that makes a handler concrete. With
`base_property = "store"`, `RESTOptions.setup` runs only when `Meta.store` is
set. This keeps `DictRESTHandler` itself abstract. Without it, the base class
would be treated as a concrete handler and get its own name and schema.

Other option hooks:

| Attribute | Use |
| --------- | --- |
| `filters_cls` | filter factory for the backend query language |
| `sorting_cls` | sorter factory for the backend query language |
| `schema_base` | base class for generated schemas |
| `schema_fields` | fields added to the generated schema |
| `schema_meta` | extra `Meta` for the generated schema |
| `schema_unknown` | Marshmallow `unknown` policy |

Override `setup` when the backend needs to derive `name`, validate a required
option, or cache a client:

```python
class DictOptions(RESTOptions):
    base_property = "store"

    def setup(self, cls):
        self.name = self.name or "items"
        super().setup(cls)
```

## Collection and resource

`prepare_collection` returns the object the rest of the pipeline understands.
For a dict it is a list. For a database it is a query, cursor, or chain.

`prepare_resource` runs on every request. It returns `None` when the path has no
`{id}`, and raises `APIError.NOT_FOUND` when the id does not match. Look it up
through `self.collection`, not the raw store, so filters and scoping from
`prepare_collection` still apply:

```python
async def prepare_resource(self, request):
    key = request["path_params"].get("id")
    if not key:
        return None

    for item in self.collection:
        if item["id"] == key:
            return item

    raise APIError.NOT_FOUND("Resource not found")
```

If the id format is invalid, raise `APIError.BAD_REQUEST` instead. The Peewee
backend does this for values that cannot be converted to the key type.

## Pagination

`paginate` is called only when `Meta.limit` is greater than zero. It receives the
already filtered and sorted `self.collection` and returns `(page, total)`:

```python
async def paginate(self, request, *, limit=0, offset=0):
    total = len(self.collection) if self.meta.limit_total else None
    return self.collection[offset : offset + limit], total
```

Return `None` for the total when `limit_total = False`; `RESTBase` then omits
the `x-total` header. For a real database, apply the limit and offset in the
query and run a separate count query. If counting is expensive, respect
`limit_total` and skip it.

## Saving

`save` receives validated data, not a raw request body. It must return the
record that will be serialized back:

```python
async def save(self, request, resource, *, update=False):
    if not update:
        resource["id"] = uuid4().hex
    self.meta.store[resource["id"]] = resource
    return resource
```

For updates, the loaded data usually does not contain every field. The base
`load` does not merge it with the existing record, so override `load`:

```python
async def load(self, request, resource=None, **options):
    data = await super().load(request, resource=resource, **options)
    if resource is not None:
        return {**resource, **data}
    return data
```

The SQLAlchemy and Mongo backends do this inside their schemas instead; see
[Schemas](schemas.md). Either place works, as long as `save(update=True)`
receives the full record.

`save_many` loops over `save` by default. Override it for a real bulk insert or
to wrap the batch in a transaction.

## Deleting

`remove` gets the loaded record for a detail request and `None` for a collection
request. In the second case the body is a JSON array of ids:

```python
async def remove(self, request, resource=None):
    if resource is not None:
        self.meta.store.pop(resource["id"], None)
        return resource["id"]

    ids = await request.data()
    if not ids:
        raise APIError.NOT_FOUND()

    for key in ids:
        self.meta.store.pop(key, None)
    return ids
```

The return value becomes the JSON response body. Peewee returns ids; SQLAlchemy
and Mongo return `null`. Pick one and document it, or override `delete` if the
default response shape does not fit.

## Reading the collection

`RESTBase.get` serializes `self.collection` directly. That works when
`prepare_collection` returns a list. When it returns a lazy query, override
`get` to execute it first:

```python
async def get(self, request, *, resource=None):
    if resource:
        return await self.dump(request, resource)

    rows = await self.meta.client.fetch_all(self.collection)
    return await self.dump(request, rows, many=True)
```

The SQLAlchemy, Mongo, and Peewee handlers all override `get` for this reason.
The same applies to any other operation that needs to materialize the query.

## Filters and sorting

The generic `Filter` and `Filters` work on dicts and objects through
`get_value`, so the dict backend needs no filter class. The generic `Sort` uses
`getattr`, which does not work on dicts, hence `DictSort` above.

For a real query language, subclass the backend filter and sorter:

```python
from muffin_rest.filters import Filter

class ClientFilter(Filter):
    async def filter(self, collection, *ops, **ctx):
        return collection.where(self.field, *ops)
```

```python
from muffin_rest.sorting import Sort

class ClientSort(Sort):
    async def apply(self, collection, *, desc=False, **ctx):
        return collection.order_by(self.field, desc=desc)
```

These sketches assume the filter stores its column in `self.field`; the Peewee
and SQLAlchemy filters do. Then point the options at them:

```python
class ClientOptions(RESTOptions):
    filters_cls = ClientFilters
    sorting_cls = ClientSorting
```

`Sorting.prepare` is the place to clear an existing order before applying the
request order. `Sorting.sort_default` applies entries marked with
`{"default": ...}` when the request has no `sort` parameter. Both are optional;
the defaults work for in-memory collections, but not for dicts (hence the
override in `DictSorting`).

## Schemas and OpenAPI

`RESTHandler` includes `OpenAPIMixin`, so a backend that subclasses it gets the
spec for free. `Meta.name` becomes the URL segment and the OpenAPI tag, and the
generated schema becomes the component.

For a model-driven backend, set `schema_base` and add the model to the schema
`Meta`:

```python
class ClientOptions(RESTOptions):
    schema_base = ClientSchema

    def setup_schema_meta(self, _):
        return type("Meta", (object,), {
            "unknown": self.schema_unknown,
            "model": self.model,
        })
```

Override `get_schema` when the schema needs the loaded record for updates:

```python
def get_schema(self, request, *, resource=None, **options):
    return super().get_schema(request, resource=resource, instance=resource, **options)
```

The Peewee, SQLAlchemy, and Mongo handlers do this. If your `load` merges the
record itself, you do not need it.

If you subclass `RESTBase` instead of `RESTHandler`, add the OpenAPI mixin
explicitly:

```python
from muffin_rest.handler import RESTBase
from muffin_rest.openapi import OpenAPIMixin

class ClientHandler(OpenAPIMixin, RESTBase):
    ...
```

## Testing

Test the backend through the HTTP layer, not only through the client methods:

```python
from asgi_tools.tests import ASGITestClient

async def test_items(app):
    client = ASGITestClient(app)
    async with client.lifespan():
        response = await client.post("/api/items", json={"name": "a"})
        assert response.status_code == 200

        item = await response.json()
        response = await client.get("/api/items")
        assert await response.json() == [item]

        response = await client.put(f"/api/items/{item['id']}", json={"count": 2})
        assert (await response.json())["count"] == 2

        response = await client.delete(f"/api/items/{item['id']}")
        assert response.status_code == 200
```

Pin the async library for backend tests:

```python
import pytest

@pytest.fixture(scope="module")
def aiolib():
    return "asyncio", {"loop_factory": None}
```

Cover at least these cases:

- create, list, detail, update, delete
- unknown id returns `404`
- invalid body returns `400`
- filter, sort, and pagination headers
- batch create and batch delete
- OpenAPI contains the resource paths

## Checklist

| Piece | Required | Notes |
| ----- | -------- | ----- |
| `meta_class` | yes | subclass `RESTOptions` |
| `base_property` | yes | the `Meta` key that makes a handler concrete |
| `prepare_collection` | yes | return the backend query or list |
| `prepare_resource` | yes | `None` for collection, `404` for missing |
| `paginate` | yes | return page and total, or `None` |
| `save` | yes | return the record to serialize |
| `remove` | yes | detail record or batch ids |
| `load` | when updates merge | merge existing record with validated data |
| `get` | when collection is lazy | execute the query before dumping |
| `filters_cls` | when query language differs | otherwise generic filters work |
| `sorting_cls` | when query language differs | generic sort needs `getattr` |
| `schema_base` | for model schemas | `setup_schema_meta` adds model/table |
| tests | yes | HTTP-level tests catch lifecycle mistakes |

The existing backends are short. Read `muffin_rest/sqlalchemy/__init__.py` for a
query-based backend and `muffin_rest/mongo/__init__.py` for a document-based one.
