# API reference

This page lists the public objects and the signatures the library calls. The
guides explain when to use them; this is the lookup table.

## Imports

```python
from muffin_rest import API, Api, APIError, RESTHandler

from muffin_rest.peewee import PWRESTHandler
from muffin_rest.peewee.filters import PWFilter, PWFilters
from muffin_rest.peewee.sorting import PWSort, PWSorting

from muffin_rest.sqlalchemy import SARESTHandler
from muffin_rest.sqlalchemy.filters import SAFilter, SAFilters
from muffin_rest.sqlalchemy.sorting import SASort, SASorting

from muffin_rest.mongo import MongoRESTHandler
from muffin_rest.mongo.filters import MongoFilter, MongoFilters
from muffin_rest.mongo.sorting import MongoSort, MongoSorting
```

Backend imports are optional. `muffin_rest` re-exports the backend classes when
their dependencies are installed.

## API

```python
API(app=None, prefix="", *, openapi=True, servers=None, **openapi_info)
```

| Attribute | Meaning |
| --------- | ------- |
| `app` | Muffin application, or `None` until `setup` |
| `prefix` | API path prefix |
| `router` | `http_router.Router` for this API |
| `openapi` | whether the docs routes are mounted |
| `openapi_options` | `info` and `servers` passed to apispec |
| `authorize` | async callback set by `authorization` |

```python
api.setup(app, *, prefix="", openapi=None, servers=None, **openapi_info)
api.route(obj, *paths, **params)
api.authorization(auth)
```

`setup` can be called once. It mounts the router on the application and adds the
docs routes. `route` accepts a handler class or a path string. `authorization`
stores the callback and returns it unchanged, so it can be used as a decorator.

## Handlers

`RESTBase` is the lifecycle. `RESTHandler` adds the OpenAPI mixin and is the base
for custom, non-database handlers. Backend handlers add storage.

| Class | Meta key | Storage |
| ----- | -------- | ------- |
| `RESTHandler` | none | your hooks |
| `PWRESTHandler` | `model` | Peewee |
| `SARESTHandler` | `table`, `database` | SQLAlchemy Core |
| `MongoRESTHandler` | `collection` | MongoDB |

Class attributes:

```python
methods = ("get", "post", "put", "delete")
meta: RESTOptions
meta_class: type[RESTOptions]
_api: API | None
```

Instance state during a request:

```python
auth        # result of authorize()
collection  # result of prepare_collection()
filters     # parsed filters, set for GET collection
sorting     # parsed sorting, set for GET collection
```

The loaded resource is passed to the HTTP method as the `resource` keyword
argument. It is not stored on `self`.

Lifecycle methods:

```python
async def authorize(self, request) -> Any
async def prepare_collection(self, request) -> Any                  # abstract
async def prepare_resource(self, request) -> Any | None
async def filter(self, request, collection) -> tuple[Any, dict]
async def sort(self, request, collection) -> tuple[Any, dict]
async def paginate(self, request, *, limit, offset) -> tuple[Any, int | None]  # abstract
```

Pagination helpers:

```python
def paginate_prepare_params(self, request) -> tuple[int, int]
def paginate_prepare_headers(self, limit, offset, total) -> dict
```

Serialization methods:

```python
def get_schema(self, request, *, resource=None, **options) -> ma.Schema
async def load_data(self, request) -> dict | list
async def load(self, request, resource=None, **options) -> Any
async def dump(self, request, data, *, many=False) -> dict | list
```

Persistence methods:

```python
async def save(self, request, resource, *, update=False) -> Any     # abstract
async def save_many(self, request, data, *, update=False) -> list
async def remove(self, request, resource=None) -> Any               # abstract
```

HTTP methods:

```python
async def get(self, request, *, resource=None) -> Any
async def post(self, request, *, resource=None) -> Any
async def put(self, request, *, resource=None) -> Any
async def delete(self, request, *, resource=None) -> Any
```

Routing:

```python
@RESTHandler.route(*paths, methods=None, hosts=None)
```

The decorator marks a method for the handler's router. The method receives
`resource` as a keyword argument.

## Options

Every backend reads these from `Meta`:

| Option | Default |
| ------ | ------- |
| `name` | table, collection, or class name |
| `limit` | `0` |
| `limit_min` | `1` |
| `limit_max` | `limit` |
| `limit_total` | `True` |
| `filters` | `()` |
| `sorting` | `()` |
| `Schema` | generated |
| `schema_base` | backend default |
| `schema_fields` | `{}` |
| `schema_meta` | `{}` |
| `schema_unknown` | `ma.EXCLUDE` |

Backend options:

| Backend | Options |
| ------- | ------- |
| Peewee | `model`, `manager`, `model_pk`, `delete_recursive` |
| SQLAlchemy | `table`, `database`, `table_pk` |
| Mongo | `collection`, `collection_id`, `aggregate` |

See [Backends](backends.md) for required fields and defaults.

## Filters

```python
FILTERS_PARAM = "where"

Filter(name, *, schema_field=None, operator=None, **meta)
Filters(handler, params)
```

| Member | Meaning |
| ------ | ------- |
| `operators` | mapping of operator name to a callable |
| `list_ops` | operators whose value is a list |
| `logic_ops` | operators whose value is a list of conditions |
| `default_operator` | operator used for scalar values |
| `apply(collection, data=None, **ctx)` | parse and apply; returns `(ops, collection)` |
| `filter(collection, *ops, **ctx)` | apply parsed operators |
| `parse(data)` | return a tuple of `(operator, value)` |
| `get_simple_value(ops)` | value of a scalar filter |
| `Filters.apply(request, collection, **ctx)` | read `where` and apply all filters |
| `Filters.convert(obj, **meta)` | build a filter from a config entry |
| `Filters.openapi` | query parameter description |

## Sorting

```python
SORT_PARAM = "sort"

Sort(name, **meta)
Sorting(handler, params)
to_sort(sort_params)
```

| Member | Meaning |
| ------ | ------- |
| `Sort.apply(collection, *, desc=False, **ctx)` | sort the collection |
| `Sorting.apply(request, collection, **ctx)` | read `sort`; returns `(collection, dict)` |
| `Sorting.prepare(collection)` | reset existing ordering before applying (Peewee) |
| `Sorting.convert(obj, **meta)` | build a sorter from a config entry |
| `Sorting.sort_default(collection)` | apply default sorting |
| `Sorting.default` | list of sorters marked `default` |
| `Sorting.openapi` | query parameter description |

## Limits

```python
RateLimiter(limit, *, period=60, **opts)
MemoryRateLimiter(limit, **opts)
RedisRateLimiter(limit, *, redis, **opts)

await limiter.check(key) -> bool
```

`check` returns `True` while the key is under the limit and `False` after.
`MemoryRateLimiter` is process-local. `RedisRateLimiter` uses `incr` and
`expire`.

## Schemas

```python
EnumField(enum, *, by_value=True, **kwargs)
load_data(data, schema=None, **params)

CompositePKField(model, **kwargs)
composite_key_to_id(fields, instance, _)
id_to_composite_keys(pk, id_)
SEPARATOR = "::"
```

`EnumField` serializes enum values and validates on load. `load_data` raises
`APIError.BAD_REQUEST` with `errors` when Marshmallow validation fails.
`CompositePKField` renders a Peewee composite key as one string id.

## OpenAPI

```python
render_openapi(api, request=None) -> dict
OpenAPIMixin.openapi(route, spec, tags) -> dict
```

`render_openapi` builds or returns the cached spec. `OpenAPIMixin` is the class
that adds `openapi` to `RESTHandler`.

## Errors

```python
APIError(content=None, *, status_code=400, **json_data)
InvalidEnpointError
HandlerNotBindedError
```

`APIError` is a JSON response and a `BaseException` subclass. Status shortcuts
come from `HTTPStatus`: `APIError.NOT_FOUND()`, `APIError.CONFLICT("...")`, and
so on.

## Query parameters

| Parameter | Applies to | Meaning |
| --------- | ---------- | ------- |
| `where` | list | JSON filter object |
| `sort` | list | comma-separated fields, `-` for descending |
| `limit` | list, when `Meta.limit` | page size |
| `offset` | list, when `Meta.limit` | page offset |
| `schema_only` | all | comma-separated fields to keep |
| `schema_exclude` | all | comma-separated fields to drop |

Response headers:

| Header | Meaning |
| ------ | ------- |
| `x-limit` | applied page size |
| `x-offset` | applied offset |
| `x-total` | total rows, unless disabled |

## Status codes

| Code | When |
| ---- | ---- |
| `200` | every successful operation, including create |
| `400` | invalid JSON, validation error, bad pagination, bad Peewee id |
| `401` | authorization callback returned a falsy value |
| `404` | unknown resource, invalid Mongo id, missing resource on `PUT` |
| `405` | method not in `methods` |
| `429` | raised by a rate limiter |
