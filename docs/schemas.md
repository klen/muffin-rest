# Schemas

Schemas do two jobs: validate incoming data and serialize outgoing resources.
Each backend generates one from the model or table, and you can replace it or
extend it.

## The generated schema

`Meta.Schema` is created when you do not provide one. The name is
`{Meta.name.title()}Schema`, and the base class comes from the backend:

| Backend | Base | Fields come from |
| ------- | ---- | ---------------- |
| `RESTHandler` | `marshmallow.Schema` | `schema_fields` only |
| Peewee | `marshmallow_peewee.ModelSchema` | the model |
| SQLAlchemy | `SQLAlchemyAutoSchema` | the table |
| Mongo | `MongoSchema` | `_id` plus `schema_fields` |

A plain `RESTHandler` has no model, so its generated schema has no fields. Add
them with `schema_fields` or a custom `Schema`.

```python
class Pets(RESTHandler):
    class Meta:
        name = "pet"
        schema_fields = {
            "name": ma.fields.String(required=True),
            "age": ma.fields.Integer(),
        }
```

For Mongo, the same pattern is the normal case:

```python
class Pets(MongoRESTHandler):
    class Meta:
        collection = pets
        schema_fields = {
            "name": ma.fields.String(required=True),
            "status": ma.fields.String(),
        }
```

## Custom schemas

Pass a schema class in `Meta`:

```python
class PetSchema(ma.Schema):
    name = ma.fields.String(required=True)
    status = ma.fields.String(load_default="available")

class Pets(PWRESTHandler):
    class Meta:
        model = Pet
        Schema = PetSchema
```

The schema is used for both `dump` and `load`. It also becomes the OpenAPI
component for the resource.

A schema can be nested inside `Meta`:

```python
class Pets(RESTHandler):
    class Meta:
        name = "pet"

        class Schema(ma.Schema):
            name = ma.fields.String(required=True)
```

## Schema options

`schema_base`, `schema_fields`, and `schema_meta` control the generated schema
without writing one:

```python
class Pets(PWRESTHandler):
    class Meta:
        model = Pet
        schema_base = MyModelSchema
        schema_fields = {"extra": ma.fields.String()}
        schema_meta = {"dump_only": ("created_at",)}
        schema_unknown = ma.EXCLUDE
```

`schema_unknown` maps to Marshmallow's `unknown` option. The default is
`EXCLUDE`, so unknown request fields are dropped silently. Use `INCLUDE` to keep
them or `RAISE` to reject them.

`schema_meta` is merged into the generated `Meta`. For Peewee and SQLAlchemy it
can override generated settings such as `model`, `table`, `include_fk`, or
`dump_only`. For Mongo it only carries options understood by `MongoSchema`.

## Validation

Incoming data is validated by `load`. A validation error returns `400` with the
Marshmallow messages:

```json
{
  "error": true,
  "message": "Bad request data",
  "errors": {"name": ["Missing data for required field."]}
}
```

Invalid JSON returns `400` with the parser message and no `errors` key.

On create, required fields must be present. On update (`PUT`, or `POST` with an
id), the schema is loaded with `partial=True`, so missing fields keep their
current values.

SQLAlchemy fills column defaults on create before the insert. Peewee and Mongo
use their own defaults.

## Reading and writing data

The default pipeline is:

```
request body -> load_data -> schema.load -> save -> schema.dump -> response
```

Override `load_data` when the body is not plain JSON:

```python
async def load_data(self, request):
    return await request.form()
```

Override `load` to change validation options or post-process the result:

```python
async def load(self, request, resource=None, **options):
    data = await super().load(request, resource=resource, **options)
    data["updated_by"] = self.auth
    return data
```

Override `dump` to add computed fields or reshape the response:

```python
async def dump(self, request, data, *, many=False):
    result = await super().dump(request, data, many=many)
    if many:
        for item in result:
            item["url"] = f"/api/pet/{item['id']}"
    else:
        result["url"] = f"/api/pet/{result['id']}"
    return result
```

`get_schema` is the single place where the schema is instantiated. Override it
to add constructor options:

```python
def get_schema(self, request, *, resource=None, **options):
    options.setdefault("context", {"request": request})
    return super().get_schema(request, resource=resource, **options)
```

## Field selection

`schema_only` and `schema_exclude` are applied inside `get_schema`:

```
GET /api/pet?schema_only=id,name
GET /api/pet?schema_exclude=password
```

Because the same schema instance is used for input and output, the selection
affects both. This trims responses and limits what a request body can write,
but it is not access control: the client chooses the query parameter. Enforce
permissions in `authorize` or in the write hooks.

## Enum fields

`muffin_rest.schemas.EnumField` serializes an enum by value and validates on
deserialize:

```python
import enum
from muffin_rest.schemas import EnumField

class Status(enum.Enum):
    AVAILABLE = "available"
    SOLD = "sold"

class PetSchema(ma.Schema):
    status = EnumField(Status)
```

Pass `by_value=False` to use enum names instead of values. Peewee fields from
`muffin_peewee` (`StrEnumField`, `IntEnumField`) are converted to this field
automatically.

## Backend notes

Peewee schemas can return model instances from `post_load`, which is useful for
creating related records. SQLAlchemy and Mongo schemas merge the loaded data
into the existing row or document on update. See [Backends](backends.md) for
the exact behavior.
