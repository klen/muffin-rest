"""Support Muffin-Peewee."""
import peewee as pw
from muffin_rest import RESTHandler, RESTNotFound, Filter, Filters, RESTOptions

try:
    from marshmallow_peewee import ModelSchema
except ImportError:
    import logging
    logging.error('Marshmallow-Peewee should be installed to use the integration.')
    raise


class PWFilter(Filter):

    """Filter Peewee Queryset."""

    operators = Filter.operators
    operators['$in'] = lambda f, v: f << v
    operators['$none'] = lambda f, v: f >> v
    operators['$like'] = lambda f, v: f % v
    operators['$contains'] = lambda f, v: f.contains(v)
    operators['$starts'] = lambda f, v: f.startswith(v)
    operators['$ends'] = lambda f, v: f.endswith(v)
    operators['$between'] = lambda f, v: f.between(*v)
    operators['$regexp'] = lambda f, v: f.regexp(v)

    list_ops = Filter.list_ops + ('$between',)

    def __init__(self, name, mfield=None, **kwargs):
        self.mfield = mfield
        return super(PWFilter, self).__init__(name, **kwargs)

    def apply(self, collection, ops, resource=None, **kwargs):
        """Filter given collection."""
        mfield = self.mfield or resource.meta.model._meta.fields.get(self.field.attribute)
        if mfield:
            collection = collection.where(*[op(mfield, val) for op, val in ops])
        return collection


class PWFilters(Filters):

    """Bind filter class."""

    FILTER_CLASS = PWFilter


class PWRESTOptions(RESTOptions):

    """Generate schema and name."""

    def __init__(self, cls, name=None, **params):
        """Initialize options."""
        super(PWRESTOptions, self).__init__(cls, **params)

        cls.name = name or self.model and self.model._meta.db_table or cls.name

        if not self.model:
            return None

        self.model_pk = self.model_pk or self.model._meta.primary_key

        if not cls.Schema:
            meta = type('Meta', (object,), dict({'model': self.model}, **self.schema_meta))
            cls.Schema = type(
                cls.name.title() + 'Schema', (self.schema_cls,),
                dict({'Meta': meta}, **self.schema))

        # Resetup filters
        if getattr(self.meta, 'filters', None):
            self.filters = self.filters_converter(*self.meta.filters, handler=cls)

        # Resetup sorting
        self.sorting = dict(
            (isinstance(n, pw.Field) and n.name or n, prop)
            for (n, prop) in self.sorting.items())


class PWRESTHandler(RESTHandler):

    """Support REST for Peewee."""

    OPTIONS_CLASS = PWRESTOptions

    class Meta:

        """Peewee options."""

        filters_converter = PWFilters

        model = None
        model_pk = None

        schema = {}
        schema_cls = ModelSchema

    def get_many(self, request, **kwargs):
        """Get collection."""
        return self.meta.model.select()

    def get_one(self, request, **kwargs):
        """Load a resource."""
        resource = request.match_info.get(self.name)
        if not resource:
            return None

        try:
            return self.collection.where(self.meta.model_pk == resource).get()
        except Exception:
            raise RESTNotFound(reason='Resource not found.')

    def sort(self, *sorting, **kwargs):
        """Sort resources."""
        sorting_ = []
        for name, desc in sorting:
            field = self.meta.sorting[name]
            if not isinstance(field, pw.Field):
                field = self.meta.model._meta.fields.get(name)

            if field is None:
                continue

            if desc:
                field = field.desc()

            sorting_.append(field)

        if sorting_:
            return self.collection.order_by(*sorting_)

        return self.collection

    def paginate(self, request, offset=0, limit=None):
        """Paginate queryset."""
        return self.collection.offset(offset).limit(limit), self.collection.count()

    def get_schema(self, request, resource=None, **kwargs):
        """Initialize schema."""
        return self.Schema(instance=resource)

    def save(self, request, resource=None, **kwargs):
        """Create a resource."""
        resources = resource if isinstance(resource, list) else [resource]
        for obj in resources:
            obj.save()
        return resource

    async def delete(self, request, resource=None, **kwargs):
        """Delete a resource.

        Supports batch delete.
        """
        if resource:
            resources = [resource]
        else:
            data = await self.parse(request)
            if data:
                resources = list(self.collection.where(self.meta.model_pk << data))

        if not resources:
            raise RESTNotFound(reason='Resource not found')

        for resource in resources:
            resource.delete_instance()
