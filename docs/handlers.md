# Handlers and lifecycle

A handler owns one resource. It receives a request, loads what the request
refers to, runs the query pipeline, and calls the HTTP method. Every part is a
method you can override.

`RESTHandler` is the base for non-database resources and adds OpenAPI support.
The backend handlers (`PWRESTHandler`, `SARESTHandler`, `MongoRESTHandler`)
extend `RESTBase` and implement the storage parts. For a custom in-memory
resource, subclass `RESTHandler` and implement `prepare_collection`.

## Binding routes

```python
@api.route
class Pets(PWRESTHandler):
    class Meta:
        model = Pet
```

Without a path, `api.route` binds two routes from `Meta.name`:

- `/{name}` for the collection
- `/{name}/{id}` for one resource

With explicit paths, only those paths are bound:

```python
@api.route("/pets", "/pets/{id}")
class Pets(PWRESTHandler):
    class Meta:
        model = Pet
```

The detail route must use `{id}`. The default `prepare_resource` reads that
parameter, and the backend handlers use it to look up the record. A different
name such as `{pet}` will leave `resource` as `None` and turn detail requests
into collection requests.

`api.route` also accepts plain functions. They are not resources and get no
query handling:

```python
@api.route("/health")
async def health(request):
    return {"status": "ok"}
```

## What runs on a request

`RESTBase.__call__` is the entry point. It runs in this order:

```
authorize(request)
prepare_collection(request)
prepare_resource(request)
    |
    +-- GET collection -> filter -> sort -> paginate -> get
    +-- GET detail     -> get(resource=...)
    +-- POST/PUT/DELETE -> the matching method with resource
    +-- custom route   -> the decorated method with resource
```

`GET` on the collection is the only path that runs filters, sorting, and
pagination. Detail requests and writes receive the loaded resource directly.
Custom routes always dispatch straight to the method, so they do not inherit
`where`, `sort`, or pagination.

The handler instance is created per request, so `self.auth` and
`self.collection` hold that request's state. `self.filters` and `self.sorting`
are filled when the collection pipeline runs.

## Methods and status codes

| Request | Method called | Notes |
| ------- | ------------- | ----- |
| `GET /name` | `get(request)` | filters, sorts, paginates |
| `GET /name/{id}` | `get(request, resource=...)` | `404` when missing |
| `POST /name` | `post(request, resource=None)` | body may be an object or an array |
| `POST /name/{id}` | `post(request, resource=...)` | updates the resource |
| `PUT /name/{id}` | `put(request, resource=...)` | partial update |
| `PUT /name` | `put(request, resource=None)` | `404` |
| `DELETE /name/{id}` | `delete(request, resource=...)` | removes one |
| `DELETE /name` | `delete(request, resource=None)` | body is an array of ids |

A create returns `200`, not `201`. The default allowed methods are `get`,
`post`, `put`, and `delete`. Other methods return `405` until you add them:

```python
class Pets(PWRESTHandler):
    methods = ("get", "post", "put", "delete", "patch")

    async def patch(self, request, *, resource=None):
        ...
```

`methods` is also used when the routes are bound, so adding a method to the
tuple without defining it is a runtime error on the first matching request.

## Hooks

Override these methods to change behavior. The signatures are the ones the base
class calls.

### Loading

```python
async def authorize(self, request) -> Any
async def prepare_collection(self, request) -> collection
async def prepare_resource(self, request) -> resource | None
```

`authorize` proxies to `API.authorize` and raises `APIError.UNAUTHORIZED` when
the callback returns a falsy value. The result is stored in `self.auth`.

`prepare_collection` is abstract. It returns the query object the backend
understands: a Peewee query, a SQLAlchemy `Select`, a `MongoChain`, or any
iterable for `RESTHandler`.

`prepare_resource` reads `request["path_params"]["id"]`. The default returns the
raw string; backend handlers resolve it and raise `404` when the record does not
exist. It runs for collection requests too, where it returns `None`.

### Query pipeline

```python
async def filter(self, request, collection) -> tuple[collection, dict]
async def sort(self, request, collection) -> tuple[collection, dict]
async def paginate(self, request, *, limit, offset) -> tuple[collection, int | None]
```

`filter` and `sort` delegate to `Meta.filters` and `Meta.sorting` and return the
parsed parameters alongside the collection. `paginate` returns the page and the
total count, or `None` when the count was skipped. `paginate` is only called
when `Meta.limit` is non-zero.

Pagination parameters are prepared by:

```python
def paginate_prepare_params(self, request) -> tuple[int, int]
def paginate_prepare_headers(self, limit, offset, total) -> dict
```

The first clamps `limit` to `[limit_min, limit_max]` and turns a negative
`offset` into `0`. The second builds `x-limit`, `x-offset`, and `x-total`.

### Serialization

```python
def get_schema(self, request, *, resource=None, **options) -> marshmallow.Schema
async def load_data(self, request) -> dict | list
async def load(self, request, resource=None, **options) -> resource | list
async def dump(self, request, data, *, many=False) -> dict | list
```

`get_schema` applies `schema_only` and `schema_exclude` from the query string
and instantiates `Meta.Schema`. `load_data` reads the request body and turns
invalid JSON into a `400`. `load` validates the body with the schema and uses
`partial=True` when a resource is present. `dump` serializes with the same
schema, so field selection affects responses and request bodies equally.

### Persistence

```python
async def save(self, request, resource, *, update=False) -> resource
async def save_many(self, request, data, *, update=False) -> list
async def remove(self, request, resource=None) -> Any
```

`save` is abstract in `RESTBase` and implemented by each backend. `save_many`
loops over `save` by default. Override it when the database supports a real bulk
insert.

`remove` receives the loaded resource for detail deletes and `None` for
collection deletes. In the second case it reads the JSON array of ids from the
request body.

## Batch operations

`POST` accepts an array:

```bash
curl -X POST http://localhost:8000/api/pet \
  -H 'content-type: application/json' \
  -d '[{"name": "Muffin"}, {"name": "Cookie"}]'
```

The body is validated with `many=True`, saved through `save_many`, and returned
as an array. `DELETE` on the collection takes an array of ids:

```bash
curl -X DELETE http://localhost:8000/api/pet \
  -H 'content-type: application/json' \
  -d '["1", "2"]'
```

Peewee returns the deleted ids. SQLAlchemy and Mongo return `null`. The methods
are sequential by default; wrap them in a transaction in `save_many` or
`remove` if a partial batch must not be visible.

## Custom routes

Decorate a method with the handler's `route`:

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

The method is bound to the API router and added to the OpenAPI spec. It receives
`resource` when the path contains `{id}`. Custom routes bypass the collection
pipeline, so call `self.filter`, `self.sort`, or `self.paginate` yourself if you
need them.

`route` accepts multiple paths and standard router options:

```python
@PWRESTHandler.route("/pet/featured", "/pet/popular", methods="get")
async def featured(self, request, *, resource=None):
    ...
```

## Overriding CRUD

The simplest way to change behavior is to override a hook, not the HTTP method.
For example, scope every query to the current user:

```python
async def prepare_collection(self, request):
    return super().prepare_collection(request).where(Pet.owner == self.auth)
```

Override `get`, `post`, `put`, or `delete` only when the response shape must
change:

```python
async def post(self, request, *, resource=None):
    response = await super().post(request, resource=resource)
    if resource is None:
        response.status_code = 201
    return response
```

Backend `get` implementations return serialized data, not a `Response`, so
wrap them yourself if you need to change headers.

Backend `delete` implementations differ. In `PWRESTHandler`, `delete` calls
`remove`, so overriding `remove` is enough. In `SARESTHandler`, `delete` is an
alias to `remove` created at class definition; overriding `remove` in a subclass
does not change `delete`. In `MongoRESTHandler`, `delete` is the implementation.
When in doubt, override `delete` as well.

## Typing

Handlers are generic over the resource and collection types:

```python
class Pets(PWRESTHandler[Pet]):
    class Meta:
        model = Pet
```

This types the `resource` argument and `self.collection` for type checkers and
gives `Meta` the backend-specific fields. The generic is optional at runtime.
