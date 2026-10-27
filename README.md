# Muffin-REST

Muffin-REST adds REST resources to [Muffin](https://github.com/klen/muffin). Describe
a model or table in a handler's `Meta` and get list and detail endpoints with
filtering, sorting, pagination, and an OpenAPI spec generated from the handlers
themselves. Backends for Peewee, SQLAlchemy Core, and MongoDB share the same
handler API, so switching storage does not change your routes.

[![Tests Status](https://github.com/klen/muffin-rest/workflows/tests/badge.svg)](https://github.com/klen/muffin-rest/actions)
[![PyPI Version](https://img.shields.io/pypi/v/muffin-rest)](https://pypi.org/project/muffin-rest/)
[![Python Versions](https://img.shields.io/pypi/pyversions/muffin-rest)](https://pypi.org/project/muffin-rest/)

## Requirements and installation

Python >= 3.11 and a Muffin application.

```bash
pip install muffin-rest                # core
pip install "muffin-rest[peewee]"      # Peewee ORM
pip install "muffin-rest[sqlalchemy]"  # SQLAlchemy Core
pip install "muffin-rest[yaml]"        # YAML in docstrings for the OpenAPI spec
```

The Mongo backend needs `muffin-mongo`; it is not an extra of this package.

## Quickstart (Peewee)

```python
from muffin import Application
from muffin_rest import API
from muffin_rest.peewee import PWRESTHandler

from models import User

app = Application("myapp")
api = API(title="User Service", version="1.0")

@api.route
class Users(PWRESTHandler):
    class Meta:
        model = User
        filters = "name", "email"
        sorting = "name", ("created_at", {"default": "desc"})
        limit = 20

api.setup(app, prefix="/api")
```

`api.route` without a path derives the URLs from `Meta.name`, which defaults to
the model's table name:

| Method   | Path                  | Action                                  |
| -------- | --------------------- | --------------------------------------- |
| `GET`    | `/api/user`           | list, with filter/sort/pagination       |
| `POST`   | `/api/user`           | create one resource or a list of them   |
| `GET`    | `/api/user/{id}`      | retrieve                                |
| `PUT`    | `/api/user/{id}`      | update; same code path as `POST`        |
| `DELETE` | `/api/user/{id}`      | delete                                  |

Create returns `200` with the serialized resource. Delete returns `200` too, with
the deleted id or ids for Peewee, and `null` for SQLAlchemy and Mongo. Handlers
answer `405` for methods outside `get`, `post`, `put`, `delete` unless you add
them to `methods`.

## Backends

Each backend reads its own `Meta` fields and keeps the same routes, filters, and
query parameters.

```python
from muffin_rest.sqlalchemy import SARESTHandler

@api.route
class Pets(SARESTHandler):
    class Meta:
        table = pet_table
        database = db
```

```python
from muffin_rest.mongo import MongoRESTHandler

@api.route
class Pets(MongoRESTHandler):
    class Meta:
        collection = mongo_collection
        aggregate = [{"$match": {"status": "available"}}]  # optional pipeline
```

The Peewee handler needs a `peewee_aio` model (`AIOModel`) with a manager, or an
explicit `Meta.manager`. Composite primary keys are supported and serialize as a
single `id` string.

## Handler options

Options live in the handler's `Meta` class. Every backend inherits these:

| Option           | Default                  | Meaning                                                   |
| ---------------- | ------------------------ | --------------------------------------------------------- |
| `name`           | table or collection name | URL segment and OpenAPI tag                               |
| `limit`          | `0`                      | Default page size; `0` disables pagination                |
| `limit_min`      | `1`                      | Smallest `limit`; `0` allows `limit=0` (all rows)         |
| `limit_max`      | `limit`                  | Largest accepted `limit`                                  |
| `limit_total`    | `True`                   | Count rows for the `x-total` header                       |
| `filters`        | `()`                     | Allowed `where` fields                                    |
| `sorting`        | `()`                     | Allowed `sort` fields                                     |
| `Schema`         | auto                     | Marshmallow schema; generated from the model when omitted |
| `schema_unknown` | `EXCLUDE`                | Marshmallow `unknown` policy                              |

## Filtering

Clients filter with the `where` query parameter, a JSON object of field names
and values:

```
GET /api/user?where={"name": "muffin", "age": {"$gt": 18}}
```

Only fields listed in `Meta.filters` are applied. These operators work on all
three backends:

| Operator                        | Meaning                     |
| ------------------------------- | --------------------------- |
| `$eq`, `==`                     | equal (the default)         |
| `$ne`, `!=`                     | not equal                   |
| `$lt`, `$le`, `$lte`, `<`, `<=` | less than                   |
| `$gt`, `$ge`, `$gte`, `>`, `>=` | greater than                |
| `$in`, `<<`                     | value is in a list          |
| `$nin`                          | value is not in a list      |
| `$starts`, `$ends`              | prefix and suffix match     |

Each backend adds operators backed by its query language:

| Backend    | Extra operators                                                         |
| ---------- | ----------------------------------------------------------------------- |
| Peewee     | `$like`, `$ilike`, `$contains`, `$regexp`, `$between`, `$null`, `$none` |
| SQLAlchemy | `$like`, `$ilike`, `$notlike`, `$notilike`, `$match`, `$between`        |
| Mongo      | none beyond the list above                                              |

`$or`, `$and`, `$not`, and `$nor` combine a list of conditions on Peewee and
SQLAlchemy. Mongo accepts only the `$`-prefixed names above, without the short
aliases. `$like` takes a SQL pattern on Peewee and SQLAlchemy; use `$starts` and
`$ends` on Mongo instead.

Filtering is deliberately forgiving. A `where` value that is not valid JSON or
not an object applies no filters, and an unknown field is ignored. If a single
value fails schema validation, only that filter is skipped; the rest still
apply. A bad `where` never fails the request, it is logged as a warning.

A custom filter class can rewrite how a field is matched by subclassing `Filter`
and passing it in `Meta.filters` as `(name, {"operator": "$like"})`.

## Sorting and pagination

`?sort=name,-created_at` sorts by the listed fields in order; a leading `-`
means descending. Fields not listed in `Meta.sorting` are ignored. A tuple entry
like `("created_at", {"default": "desc"})` also makes that field the default
order when no `sort` is given.

When `Meta.limit` is set, clients pass `limit` and `offset`. `limit` is clamped
to `[limit_min, limit_max]`, a negative `offset` becomes `0`, and invalid numbers
return `400`. Responses carry `x-limit`, `x-offset`, and, unless
`limit_total = False`, `x-total`.

## Choosing fields

`schema_only` and `schema_exclude` take comma-separated schema field names and
apply to both the response and the request body:

```
GET /api/user?schema_only=id,name
GET /api/user?schema_exclude=password
```

## Authorization

Authorization belongs to the API: one callback covers every handler, and its
docstring feeds the OpenAPI security scheme.

```python
@api.authorization
async def authorize(request):
    """Check the request.

    ---
    Auth:
        type: http
        scheme: bearer
    """
    return request.headers.get("authorization", "")
```

Handlers call `self.authorize(request)` by default. Override it to add per-resource
rules, and raise `APIError` when a request must be rejected:

```python
from muffin_rest import APIError
from muffin_rest.limits import MemoryRateLimiter

limiter = MemoryRateLimiter(60, period=60)  # per process; use Redis in production

class Users(PWRESTHandler):
    async def authorize(self, request):
        if not await limiter.check(request.client[0]):
            raise APIError.TOO_MANY_REQUESTS("Rate limit exceeded")
        return super().authorize(request)
```

## Custom routes

Methods decorated with `route` on a handler are added to its paths and appear in
the OpenAPI spec. The docstring is parsed as YAML, so parameters and bodies can
be described inline.

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

Use `@api.route("/health")` for plain Muffin views that are not resources.

## Errors

`APIError` returns a JSON body `{"error": true, "message": ...}` with the matching
status code. Use the status shortcuts rather than numbers:

```python
raise APIError.NOT_FOUND("No such pet")
raise APIError.BAD_REQUEST({"error": True, "message": "Invalid filter", "field": "age"})
```

## OpenAPI

`api.setup()` mounts Swagger UI, ReDoc, and the spec under the API prefix:

- `/api/swagger`
- `/api/redoc`
- `/api/openapi.json`

Pass `openapi=False` to `API()` or `api.setup()` to skip them. The `servers`
argument and any extra keyword arguments go into the spec info block:

```python
api = API(
    title="Pet Store",
    version="2.0",
    description="Pets and categories",
    servers=[{"url": "https://example.com/api"}],
)
```

## Examples and development

- `examples/peewee_orm` and `examples/sqlalchemy_core` run against a local SQLite
  database: `uvicorn examples.peewee_orm:app`
- `uv sync`, then `uv run pytest`. Mongo tests need Docker with a container named
  `mongo` (`docker start mongo`)
- `CHANGELOG.md` records what changed and when

## Bug tracker and contributing

Issues and pull requests: https://github.com/klen/muffin-rest

## Contributors

- [klen](https://github.com/klen) (Kirill Klenov)

## License

MIT. See [LICENSE](LICENSE).
