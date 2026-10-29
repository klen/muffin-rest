# Backends

All backends expose the same routes and the same query parameters. They differ
in what `Meta` requires, how schemas are generated, and what a delete returns.

## Common options

| Option | Default | Meaning |
| ------ | ------- | ------- |
| `name` | table, collection, or class name | URL segment and OpenAPI tag |
| `limit` | `0` | Default page size; `0` disables pagination |
| `limit_min` | `1` | Smallest `limit`; `0` allows `limit=0` (all rows) |
| `limit_max` | `limit` | Largest accepted `limit` |
| `limit_total` | `True` | Count rows for the `x-total` header |
| `filters` | `()` | Allowed `where` fields |
| `sorting` | `()` | Allowed `sort` fields |
| `Schema` | generated | Marshmallow schema |
| `schema_base` | backend default | Base class for the generated schema |
| `schema_fields` | `{}` | Extra fields for the generated schema |
| `schema_meta` | `{}` | Extra `Meta` options for the generated schema |
| `schema_unknown` | `EXCLUDE` | Marshmallow `unknown` policy |

`Meta` options are inherited. A subclass can override only what it needs:

```python
class BaseResource(PWRESTHandler):
    class Meta:
        limit = 20
        sorting = ("id", {"default": "desc"})


class Pets(BaseResource):
    class Meta:
        model = Pet
        filters = ("status",)
```

## Peewee

```python
from muffin_rest.peewee import PWRESTHandler

@api.route
class Pets(PWRESTHandler):
    class Meta:
        model = Pet
        manager = db.manager       # optional
        model_pk = Pet.id          # optional
        delete_recursive = False
```

| Option | Required | Meaning |
| ------ | -------- | ------- |
| `model` | yes | `peewee` model, preferably `peewee_aio` |
| `manager` | no | `peewee_aio.Manager`; defaults to `model._manager` |
| `model_pk` | no | Primary key field; defaults to `model._meta.primary_key` |
| `delete_recursive` | no | Passed to `delete_instance(recursive=...)` |

The model needs a manager. With `muffin_peewee`, `db.Model` and `db.register`
provide one. A plain `peewee.Model` works when you pass `Meta.manager`.

The generated schema uses `marshmallow_peewee.ModelSchema`, so fields, nullability,
and foreign keys come from the model. Enums built with `muffin_peewee` fields are
mapped to `muffin_rest.schemas.EnumField`, and foreign keys are exposed as
integers.

A single resource is looked up with the primary key's Python converter, so
string route params become the column type. An unknown id returns `404`; a value
that cannot be converted to the key type returns `400`.

Delete returns the deleted id for a detail request and a list of ids for a
batch request. Peewee sorters put `NULL` values last.

### Composite primary keys

A model with `peewee.CompositeKey` is addressed by a single string id built from
the key columns with `::` as the separator:

```
GET /api/pet/acme::7
```

The detail lookup splits the id and compares each column. A wrong number of
parts returns `400`. The generated schema exposes the key columns separately
(`tenant`, `seq`). To expose one `id` field, add `CompositePKField` to a custom
schema:

```python
import marshmallow as ma
from muffin_rest.peewee.schemas import CompositePKField

class PetSchema(ma.Schema):
    id = CompositePKField(Pet)
```

## SQLAlchemy Core

```python
from muffin_rest.sqlalchemy import SARESTHandler

@api.route
class Pets(SARESTHandler):
    class Meta:
        table = pet_table
        database = db
        table_pk = pet_table.c.id  # optional
```

| Option | Required | Meaning |
| ------ | -------- | ------- |
| `table` | yes | `sqlalchemy.Table` |
| `database` | yes | `muffin_databases.Plugin` |
| `table_pk` | no | Primary key column; defaults to `table.c.id` |

The generated schema extends `SQLAlchemyAutoSchema`. It includes foreign keys,
marks the primary key as `dump_only`, and fills column defaults on create. This
matters because SQLAlchemy Core does not apply Python-side defaults on insert;
the schema does it before the query is executed.

Updates merge the validated body into the loaded row, so `PUT` is a partial
update. Delete returns `null` for both detail and batch requests.

## MongoDB

```python
from muffin_rest.mongo import MongoRESTHandler

@api.route
class Pets(MongoRESTHandler):
    class Meta:
        collection = mongo_collection
        collection_id = "_id"      # optional
        aggregate = None           # optional pipeline
```

| Option | Required | Meaning |
| ------ | -------- | ------- |
| `collection` | yes | Motor collection |
| `collection_id` | no | Id field, `_id` by default |
| `aggregate` | no | Base aggregation pipeline for list requests |

The generated schema extends `MongoSchema`. It defines `_id` as an `ObjectId`
field but no other fields, so declare them yourself:

```python
class PetSchema(MongoSchema):
    name = ma.fields.String(required=True)
    status = ma.fields.String()
```

or use `Meta.schema_fields`:

```python
class Meta:
    collection = pets
    schema_fields = {
        "name": ma.fields.String(required=True),
        "status": ma.fields.String(),
    }
```

`MongoSchema` merges validated data into the loaded document on update, which is
why `PUT` behaves as a partial update.

Detail ids are parsed with `bson.ObjectId`. An invalid id returns `404`. Delete
returns `null`, including batch deletes.

Collections are wrapped in `MongoChain`, a small lazy wrapper that accumulates
filters and sorting and builds a Motor cursor on demand. Filters are combined
with `$and`, sorting is appended, and `to_list()` materializes the result.

### Aggregation

`Meta.aggregate` is used for list requests when pagination is enabled
(`Meta.limit > 0`). Pagination appends `$skip` and `$limit`, and the total count
is computed with a second pipeline. Request filters are merged into the first
`$match` stage, or inserted at the front when there is none. The configured
pipeline is not modified between requests.

With `Meta.limit = 0`, list requests use a plain `find` and the pipeline is
ignored.

With an aggregation pipeline, the total is always counted; `limit_total` only
controls the count for plain `find` queries.

### Mongo filters

The Mongo filter class supports only the `$`-prefixed operators listed in
[Querying](querying.md). Short aliases such as `==` or `>` and the logic
operators `$or`, `$and`, `$not`, `$nor` are not available.

`$starts` and `$ends` build a regex from the user value and escape it, so dots
and other regex characters are literal.

To filter by `_id`, expose it with a schema field so the string is converted to
an `ObjectId`:

```python
class Meta:
    collection = pets
    filters = (("_id", {"field": "_id"}),)
```

## Delete behavior

| Backend | Detail delete returns | Batch delete returns |
| ------- | --------------------- | -------------------- |
| Peewee | the deleted id | array of deleted ids |
| SQLAlchemy | `null` | `null` |
| Mongo | `null` | `null` |

Batch delete always uses the collection route and a JSON array body. Peewee
returns `404` when no id matches; SQLAlchemy and Mongo return `200` even when
nothing was deleted.

## Choosing a backend

Use Peewee when you already have Peewee models and want model-driven schemas.
Use SQLAlchemy Core when your tables are defined with `sqlalchemy.Table` and you
use `muffin_databases`. Use Mongo when the data is document-shaped or when you
need an aggregation pipeline before pagination.

The handler API is the same, so the choice mostly affects schema generation and
the query objects you see in hooks.

If your storage is not listed here, [Writing a backend](custom-backend.md) walks
through the five methods a new backend has to implement.
