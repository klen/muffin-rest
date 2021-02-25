"""Support for Peewee ORM (https://github.com/coleifer/peewee)."""
import typing as t

import marshmallow as ma
import muffin
import peewee as pw
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from http_router.routes import Route
from marshmallow_peewee import ModelSchema, ForeignKey

from ..endpoint import Endpoint, EndpointOpts
from ..errors import APIError
from ..filters import Filter, Filters


# XXX: Patch apispec.MarshmallowPlugin to support ForeignKeyField
MarshmallowPlugin.Converter.field_mapping[ForeignKey] = ("integer", None)


class PeeweeFilter(Filter):
    """Support Peewee."""

    operators = Filter.operators
    operators['$in'] = lambda f, v: f << v
    operators['$none'] = lambda f, v: f >> v
    operators['$like'] = lambda f, v: f % v
    operators['$contains'] = lambda f, v: f.contains(v)
    operators['$starts'] = lambda f, v: f.startswith(v)
    operators['$ends'] = lambda f, v: f.endswith(v)
    operators['$between'] = lambda f, v: f.between(*v)
    operators['$regexp'] = lambda f, v: f.regexp(v)

    list_ops = Filter.list_ops + ['$between']

    def __init__(self, name: str, attr: str = None,
                 field: ma.fields.Field = None, mfield: pw.Field = None):
        """Support custom model fields."""
        super(PeeweeFilter, self).__init__(name, attr, field)
        self.mfield = mfield

    def apply(self, collection: pw.Query, ops: t.Tuple[t.Tuple[t.Callable, t.Any], ...],
              endpoint: 'PeeweeEndpoint' = None, **kwargs) -> pw.Query:
        """Apply the filters to Peewee QuerySet.."""
        mfield = (
            self.mfield or endpoint and endpoint.meta.model._meta.fields.get(self.field.attribute))
        if mfield and ops:
            collection = collection.where(*[op(mfield, val) for op, val in ops])
        return collection


class PeeweeFilters(Filters):
    """Bind Peewee filter class."""

    FILTER_CLASS = PeeweeFilter


class PeeweeEndpointOpts(EndpointOpts):
    """Support Peewee."""

    if t.TYPE_CHECKING:
        model: pw.Model
        model_pk: pw.Field
        Schema: t.Type[ModelSchema]

    def __init__(self, cls):
        """Prepare meta options."""
        noname = getattr(cls.Meta, 'name', None) is None
        super(PeeweeEndpointOpts, self).__init__(cls)
        if not self.model:
            return

        self.model_pk = self.model_pk or self.model._meta.primary_key

        if noname:
            self.name = self.model._meta.table_name
            self.name_id = self.model_pk.name

        # Setup a schema
        if self.Schema is ModelSchema:
            meta = type('Meta', (object,), dict({'model': self.model}, **self.schema_meta))
            self.Schema = type(
                self.name.title() + 'Schema', (ModelSchema,),
                dict({'Meta': meta}))

        # Setup sorting
        self.sorting = dict(
            (isinstance(n, pw.Field) and n.name or n, prop)
            for (n, prop) in self.sorting.items())


class PeeweeEndpoint(Endpoint):
    """Support Peeweee."""

    collection: pw.Query
    resource: pw.Model
    meta: PeeweeEndpointOpts
    meta_class: t.Type[PeeweeEndpointOpts] = PeeweeEndpointOpts

    class Meta:
        """Tune peewee endpoints."""

        filters_cls = PeeweeFilters

        # Peewee options
        model = None
        model_pk = None

        Schema = ModelSchema

    async def prepare_collection(self, request: muffin.Request) -> pw.Query:
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        return self.meta.model.select()

    async def prepare_resource(self, request: muffin.Request) -> t.Optional[pw.Model]:
        """Load a resource."""
        pk = request['path_params'].get(self.meta.name_id)
        if not pk:
            return None

        try:
            return self.collection.where(self.meta.model_pk == pk).get()
        except self.meta.model.DoesNotExist:
            raise APIError.NOT_FOUND('Resource not found')

    async def sort(self, request: muffin.Request,
                   *sorting: t.Tuple[str, bool], **options) -> pw.Query:
        """Sort the current collection."""
        order_by = []
        for name, desc in sorting:
            field = self.meta.sorting.get(name)
            if field and not isinstance(field, pw.Field):
                field = self.meta.model._meta.fields.get(name)

            if field is None:
                continue

            if desc:
                field = field.desc()  # type: ignore

            order_by.append(field)

        if order_by:
            return self.collection.order_by(*order_by)

        return self.collection

    async def paginate(self, request: muffin.Request, *, limit: int = 0,
                       offset: int = 0) -> t.Tuple[pw.Query, int]:
        """Paginate the collection."""
        cqs = self.collection.order_by()
        if cqs._group_by:
            cqs._select = cqs._group_by
        return self.collection.offset(offset).limit(limit), cqs.count()

    async def save(self, request: muffin.Request,  # type: ignore
                   resource: t.Union[pw.Model, t.List[pw.Model]]):
        """Save the given resource.

        Supports batch saving.
        """
        for obj in (resource if isinstance(resource, list) else [resource]):
            obj.save()
        return resource

    async def remove(self, request: muffin.Request, *, resource: pw.Model = None):
        """Remove the given resource."""
        if resource:
            resources = [resource]

        else:
            data = await request.data()
            if not data:
                return
            resources = list(self.collection.where(self.meta.model_pk << data))

        if not resources:
            raise APIError.NOT_FOUND()

        for resource in resources:
            resource.delete_instance()

    delete = remove  # noqa

    async def get_schema(self, request: muffin.Request, resource=None) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        return self.meta.Schema(
            instance=resource,
            only=request.url.query.get('schema_only'),
            exclude=request.url.query.get('schema_exclude', ()),
        ) if self.meta.Schema else None

    @classmethod
    def openapi(cls, route: Route, spec: APISpec) -> t.Dict:
        """Get openapi specs for the endpoint."""
        operations = super(PeeweeEndpoint, cls).openapi(route, spec)
        is_resource_route = getattr(route, 'params', {}).get(cls.meta.name_id)
        if not is_resource_route and 'delete' in operations:
            operations['delete'].setdefault('parameters', [])
            operations['delete']['requestBody'] = {
                'required': True,
                'content': {
                    'application/json': {'schema': {'type': 'array', 'items': {'type': 'string'}}}
                }
            }
        return operations
