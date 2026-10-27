# Muffin‑REST

**Muffin‑REST** simplifies building RESTful APIs with [Muffin](https://github.com/klen/muffin) by offering:

- Declarative `API` class with resource registration
- Built-in filtering, sorting, pagination, and search
- Support for:
  - [Peewee ORM](http://docs.peewee-orm.com/en/latest/) via `PeeweeEndpoint`
  - [SQLAlchemy Core](https://docs.sqlalchemy.org/en/14/core/) via `SAEndpoint`
  - [MongoDB](https://www.mongodb.com/) via `MongoEndpoint`
- [Swagger/OpenAPI](https://swagger.io/) autodocumentation
- Works with asyncio, Trio, and Curio

[![Tests Status](https://github.com/klen/muffin-rest/workflows/tests/badge.svg)](https://github.com/klen/muffin-rest/actions)
[![PyPI Version](https://img.shields.io/pypi/v/muffin-rest)](https://pypi.org/project/muffin-rest/)
[![Python Versions](https://img.shields.io/pypi/pyversions/muffin-rest)](https://pypi.org/project/muffin-rest/)

## Requirements

- Python >= 3.11
- Trio requires Peewee backend

## Installation

Install core package:

```bash
pip install muffin-rest
```

Add optional backend support:

- SQLAlchemy Core: `pip install muffin-rest[sqlalchemy]`
- Peewee ORM: `pip install muffin-rest[peewee]`
- YAML support for Swagger: `pip install muffin-rest[yaml]`

## Quickstart (Peewee example)

```python
from muffin import Application
from muffin_rest import API
from muffin_rest.peewee import PeeweeEndpoint
from models import User  # your Peewee model

app = Application("myapp")
api = API(title="User Service", version="1.0")

@api.route
class UsersEndpoint(PeeweeEndpoint):
    class Meta:
        model = User
        lookup_field = "id"
        filters = ["name", "email"]
        ordering = ["-created_at"]

api.setup(app, prefix="/api", swagger=True)
```

Endpoints available:

- `GET    /api/users/` — list with pagination, search, filtering
- `POST   /api/users/` — create
- `GET    /api/users/{id}/` — retrieve
- `PUT    /api/users/{id}/` — replace
- `DELETE /api/users/{id}/` — remove
- Docs: `/api/docs/`, OpenAPI spec: `/api/openapi.json`

## Usage with SQLAlchemy

```python
from muffin_rest import API
from muffin_rest.sqlalchemy import SAEndpoint
from models import my_table, db_engine

api = API()
@api.route
class MySAEndpoint(SAEndpoint):
    class Meta:
        table = my_table
        database = db_engine

api.setup(app)
```

## Usage with MongoDB

```python
from muffin_rest import API
from muffin_rest.mongo import MongoEndpoint
from models import mongo_collection

api = API()
@api.route
class MyMongoEndpoint(MongoEndpoint):
    class Meta:
        collection = mongo_collection

api.setup(app)
```

## Filtering

Pass filters in the `where` query parameter as JSON:

```
GET /api/users/?where={"name": "muffin", "age": {"$gt": 18}}
```

Invalid filter data is ignored, not rejected. If `where` is not valid JSON or
not an object, no filters are applied. If a single filter value fails its field
validation, only that filter is skipped and the others still apply.

## Pagination and sorting

Enable pagination with `limit` in `Meta`; clients then pass `limit` and
`offset` query parameters. The `limit` is clamped between `limit_min` (default
`1`) and `limit_max`; set `limit_min = 0` to allow `limit=0` to return all
rows. A negative `offset` becomes `0`.

Sort with the `sort` parameter: `?sort=name,-count`. Fields are applied in the
requested order.

`schema_only` and `schema_exclude` accept comma-separated field names to pick
which fields are serialized.

## Advanced Configuration

Customize Swagger and routes via constructor:

```python
api = API(
    title="Service API",
    version="2.1",
    swagger_ui=True,
    openapi_path="/api/openapi.json",
    docs_path="/api/docs/"
)
```

## Contributing & Examples

- See `examples/` for live application demos
- Tests in `tests/` focus on filtering, pagination, status codes
- Check `CHANGELOG.md` for latest changes

## Bug Tracker

Report bugs or request features:
https://github.com/klen/muffin-rest/issues

## Contributing

Repo: https://github.com/klen/muffin-rest
Pull requests, example additions, docs improvements welcome!

## Contributors

- [klen](https://github.com/klen) (Kirill Klenov)

## License

Licensed under the [MIT license](http://opensource.org/licenses/MIT).
