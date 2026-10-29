# Querying

List requests accept four query parameters: `where`, `sort`, `limit`/`offset`,
and `schema_only`/`schema_exclude`. Only fields declared in `Meta` are accepted.

## Filters

`where` is a JSON object of field names and values:

```
GET /api/user?where={"name": "muffin", "age": {"$gt": 18}}
```

The value can be a scalar, which means equality, or an object of operators.
Only fields listed in `Meta.filters` are applied. An unknown field is ignored.

```python
class Users(PWRESTHandler):
    class Meta:
        model = User
        filters = ("name", "age", ("created", {"field": "created_at"}))
```

Each entry can be:

- a field name: the filter name and column are the same
- a `(name, options)` tuple: `field` maps the filter name to another column,
  `schema_field` overrides the field used to deserialize values, and `operator`
  sets the default operator for scalar values
- a `Filter` instance for full control
- a Peewee `Field` or SQLAlchemy `Column` directly

Mapping a public filter name to a different column:

```python
filters = (("user", {"field": "user_id"}),)
# GET /api/order?where={"user": 42} filters on user_id
```

Changing the default operator:

```python
filters = (("name", {"operator": "$like"}),)
# GET /api/user?where={"name": "muff%"}
```

### Operators

These operators work on Peewee, SQLAlchemy, and Mongo. Mongo accepts only the
`$`-prefixed names; the aliases are for Peewee and SQLAlchemy.

| Operator | Alias | Meaning |
| -------- | ----- | ------- |
| `$eq` | `==` | equal |
| `$ne` | `!=` | not equal |
| `$lt` | `<` | less than |
| `$le` | `<=`, `$lte` | less than or equal |
| `$gt` | `>` | greater than |
| `$ge` | `>=`, `$gte` | greater than or equal |
| `$in` | `<<` | value is in a list |
| `$nin` | | value is not in a list |
| `$starts` | | string starts with |
| `$ends` | | string ends with |

Backend-specific operators:

| Backend | Extra operators |
| ------- | --------------- |
| Peewee | `$like`, `$ilike`, `$contains`, `$regexp`, `$between`, `$null`, `$none` |
| SQLAlchemy | `$like`, `$ilike`, `$notlike`, `$notilike`, `$match`, `$between` |
| Mongo | none |

`$in` and `$nin` take a list. `$between` takes a two-item list on Peewee and
SQLAlchemy, and `$null` takes a boolean on Peewee. `$like` takes a SQL pattern
on Peewee and SQLAlchemy. Mongo has no `$like`; use `$starts` and `$ends`, which
escape the value before building a regex.

Peewee's `$nin` is not implemented. Use `$not` with `$in` instead:

```json
{"name": {"$not": [{"$in": ["a", "b"]}]}}
```

### Logic operators

Peewee and SQLAlchemy support `$or`, `$and`, `$not`, and `$nor`. The value is a
list of conditions:

```json
{"age": {"$or": [{"$lt": 18}, {"$gt": 65}]}}
```

Mongo does not support these operators.

### Forgiving by design

A bad filter does not fail the request:

- invalid JSON, or a `where` value that is not an object, logs a warning and
  applies no filters
- an unknown field is ignored
- a value that fails schema validation skips that one filter; the rest still
  apply

This keeps exploratory queries from turning into `400`s. Validate the values
you care about in a custom filter if you need strict behavior.

### Custom filters

Subclass the backend filter and override `filter`:

```python
from muffin_rest.peewee.filters import PWFilter

class CaseInsensitiveFilter(PWFilter):
    async def filter(self, collection, *ops, **ctx):
        column = self.field
        return collection.where(column.ilike(f"%{ops[0][1]}%"))

class Users(PWRESTHandler):
    class Meta:
        model = User
        filters = (CaseInsensitiveFilter("name"),)
```

The base class parses values with `self.schema_field`, which is taken from the
generated schema field with the same name. Set `schema_field` explicitly when
the filter name does not match a schema field.

## Sorting

`sort` is a comma-separated list. A leading `-` means descending:

```
GET /api/user?sort=name,-created_at
```

Fields are applied in the order given. Only fields listed in `Meta.sorting` are
used; unknown fields are ignored.

```python
class Users(PWRESTHandler):
    class Meta:
        model = User
        sorting = ("name", ("created_at", {"default": "desc"}))
```

A `default` entry sets the order used when the request has no `sort` parameter.
The value `"desc"` sorts descending; any other truthy value sorts ascending.
Default sorting is not applied when a request provides its own `sort`.

Peewee sorters put `NULL` values last. SQLAlchemy and Mongo use the database's
default null ordering.

A custom sorter subclasses the backend sorter and returns the modified query:

```python
import sqlalchemy as sa
from muffin_rest.sqlalchemy.sorting import SASort

class LengthSort(SASort):
    async def apply(self, collection, *, desc=False, **ctx):
        expr = sa.func.length(self.field)
        return collection.order_by(expr.desc() if desc else expr)
```

Use `PWSort` or `MongoSort` for the other backends.

## Pagination

Pagination is active only when `Meta.limit` is greater than zero:

```python
class Users(PWRESTHandler):
    class Meta:
        model = User
        limit = 20        # default page size
        limit_min = 1
        limit_max = 100
        limit_total = True
```

```
GET /api/user?limit=50&offset=100
```

`limit` is clamped to `[limit_min, limit_max]` and `offset` to `>= 0`. Invalid
numbers return `400`. A `limit` of `0` is clamped up to `limit_min`, so it
returns one row by default. Set `limit_min = 0` to let `limit=0` return all
rows.

Responses carry:

| Header | Meaning |
| ------ | ------- |
| `x-limit` | applied page size |
| `x-offset` | applied offset |
| `x-total` | total rows, unless `limit_total = False` |

With `limit_total = False`, the backend skips the count query and the `x-total`
header. This is the usual choice for large tables where an exact count is
expensive. Mongo aggregation pipelines always compute the count.

Setting `Meta.limit = 0` disables pagination entirely: no count, no headers,
and no `limit`/`offset` handling.

## Field selection

`schema_only` and `schema_exclude` take comma-separated schema field names:

```
GET /api/user?schema_only=id,name
GET /api/user?schema_exclude=password
```

The same schema is used for responses and request bodies, so a field excluded
here is also dropped from an incoming `POST` or `PUT`. Names must exist in the
schema. Use `Meta.schema_unknown = EXCLUDE` (the default) to silently drop
unknown request fields.
