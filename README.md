# Muffin-REST

Muffin-REST turns Muffin handlers into REST resources. Describe a model or table
in a handler's `Meta` and the handler serves list and detail endpoints with
filtering, sorting, pagination, and an OpenAPI spec generated from the code.
Peewee, SQLAlchemy Core, and MongoDB backends share the same handler API, so
changing storage does not change your routes.

[![Tests Status](https://github.com/klen/muffin-rest/workflows/tests/badge.svg)](https://github.com/klen/muffin-rest/actions)
[![PyPI Version](https://img.shields.io/pypi/v/muffin-rest)](https://pypi.org/project/muffin-rest/)
[![Python Versions](https://img.shields.io/pypi/pyversions/muffin-rest)](https://pypi.org/project/muffin-rest/)

## Install

Python >= 3.11 and a Muffin application.

```bash
pip install muffin-rest                # core
pip install "muffin-rest[peewee]"      # Peewee ORM
pip install "muffin-rest[sqlalchemy]"  # SQLAlchemy Core
pip install "muffin-rest[yaml]"        # YAML docstrings for the OpenAPI spec
```

The Mongo backend needs `muffin-mongo`; it is not an extra of this package.

## Quickstart

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

| Method   | Path             | Action                                |
| -------- | ---------------- | ------------------------------------- |
| `GET`    | `/api/user`      | list, with filter/sort/pagination     |
| `POST`   | `/api/user`      | create one resource or a list of them |
| `GET`    | `/api/user/{id}` | retrieve                              |
| `PUT`    | `/api/user/{id}` | update                                |
| `DELETE` | `/api/user/{id}` | delete                                |

Create returns `200` with the serialized resource. Delete returns `200` too, with
the deleted id or ids for Peewee, and `null` for SQLAlchemy and Mongo. Handlers
answer `405` for methods outside `get`, `post`, `put`, `delete` unless you add
them to `methods`.

## Backends

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
        limit = 20
        aggregate = [{"$match": {"status": "available"}}]  # used with pagination
```

The Peewee handler needs a `peewee_aio` model with a manager, or an explicit
`Meta.manager`. Composite primary keys are supported; the route id joins the key
columns with `::`. The Mongo handler needs `muffin-mongo`.

## Documentation

Published documentation: https://klen.github.io/muffin-rest/

The README covers the shape of the library. The guides explain the parts that
need more than a snippet:

| Guide | What it answers |
| ----- | --------------- |
| [Tutorial](https://github.com/klen/muffin-rest/blob/develop/docs/tutorial.md) | Build and run a small API from scratch |
| [Handlers and lifecycle](https://github.com/klen/muffin-rest/blob/develop/docs/handlers.md) | What runs on each request, and which hook to override |
| [Backends](https://github.com/klen/muffin-rest/blob/develop/docs/backends.md) | Peewee, SQLAlchemy, and Mongo options and differences |
| [Querying](https://github.com/klen/muffin-rest/blob/develop/docs/querying.md) | `where`, `sort`, pagination, field selection |
| [Schemas](https://github.com/klen/muffin-rest/blob/develop/docs/schemas.md) | Generated schemas, validation, custom fields |
| [OpenAPI](https://github.com/klen/muffin-rest/blob/develop/docs/openapi.md) | Spec generation, docstrings, auth, response types |
| [Errors](https://github.com/klen/muffin-rest/blob/develop/docs/errors.md) | `APIError`, validation errors, status codes |
| [Cookbook](https://github.com/klen/muffin-rest/blob/develop/docs/cookbook.md) | Auth, scoping, soft delete, custom filters and routes |
| [API reference](https://github.com/klen/muffin-rest/blob/develop/docs/reference.md) | Public classes, options, and hook signatures |
| [Development](https://github.com/klen/muffin-rest/blob/develop/docs/development.md) | Tests, linting, examples, release |

Start with the [documentation index](https://github.com/klen/muffin-rest/blob/develop/docs/index.md)
if you are browsing the repository.

## Development

```bash
uv sync                 # install dependencies
uv run pytest           # run tests
make lint               # pyrefly + ruff
make docs               # build the documentation
make docs-serve         # preview it locally
```

Mongo tests need Docker with a container named `mongo` (`docker start mongo`).
Examples run against SQLite:

```bash
uv run uvicorn examples.peewee_orm:app --reload --port=5000
uv run uvicorn examples.sqlalchemy_core:app --reload --port=5000
```

See [Development](https://github.com/klen/muffin-rest/blob/develop/docs/development.md)
for the full workflow.

## Bug tracker and contributing

Issues and pull requests: https://github.com/klen/muffin-rest

## Contributors

- [klen](https://github.com/klen) (Kirill Klenov)

## License

MIT. See [LICENSE](LICENSE).
