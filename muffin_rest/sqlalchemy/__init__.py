"""SQLAlchemy Core support."""

import typing as t

import marshmallow as ma
import muffin
import sqlalchemy as sa
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema as BaseSQLAlchemyAutoSchema, ModelConverter
from muffin._types import JSONType
from muffin_databases import Plugin as DB

from ..endpoint import Endpoint, EndpointOpts
from ..errors import APIError
from ..filters import Filter, Filters


# XXX: Monkey patch ModelConverter
ModelConverter._get_field_name = lambda s, prop_or_column: str(prop_or_column.key)


class SQLAlchemyAutoSchema(BaseSQLAlchemyAutoSchema):
    """Allow partial updates for tables."""

    @ma.post_load
    def make_instance(self, data, **kwargs):
        """Update a table instance."""
        if self.instance is not None:
            instance = dict(self.instance)
            instance.update(data)
            return instance
        return super(SQLAlchemyAutoSchema, self).make_instance(data, **kwargs)


class SAFilter(Filter):
    """Custom filter for sqlalchemy."""

    operators = Filter.operators
    operators['$between'] = lambda f, v: f.between(*v)
    operators['$ends'] = lambda c, v: c.endswith(v)
    operators['$ilike'] = lambda c, v: c.ilike(v)
    operators['$in'] = lambda c, v: c.in_(v)
    operators['$like'] = lambda c, v: c.like(v)
    operators['$match'] = lambda c, v: c.match(v)
    operators['$nin'] = lambda c, v: ~c.in_(v)
    operators['$notilike'] = lambda c, v: c.notilike(v)
    operators['$notlike'] = lambda c, v: c.notlike(v)
    operators['$starts'] = lambda c, v: c.startswith(v)

    list_ops = Filter.list_ops + ['$between']

    def __init__(self, name: str, attr: str = None,
                 field: ma.fields.Field = None, column: sa.Column = None):
        """Support custom model fields."""
        super().__init__(name, attr, field)
        self.column = column

    def apply(self, collection: sa.sql.Select, ops: t.Tuple[t.Tuple[t.Callable, t.Any], ...],
              endpoint: 'SAEndpoint' = None, **kwargs) -> sa.sql.Select:
        """Apply the filters to SQLAlchemy Select."""
        column = (self.column or endpoint and endpoint.meta.table.c.get(self.field.attribute))
        if ops and column is not None:
            collection = collection.where(*[op(column, val) for op, val in ops])

        return collection


class SAFilters(Filters):
    """Bind SAfilter class."""

    FILTER_CLASS = SAFilter


class SAEndpointOpts(EndpointOpts):
    """Support SQLAlchemy Core."""

    if t.TYPE_CHECKING:
        table: sa.Table
        table_pk: sa.Column
        database: DB
        Schema: t.Type[SQLAlchemyAutoSchema]

    def __init__(self, cls):
        """Prepare meta options."""
        noname = getattr(cls.Meta, 'name', None) is None
        super().__init__(cls)

        if self.table is None:
            return

        if self.database is None:
            raise RuntimeError('SAEndpoint.meta.database is required')

        self.table_pk = self.table_pk or self.table.c.id

        if noname:
            self.name = self.table.name
            self.name_id = self.table_pk.name

        if self.Schema is SQLAlchemyAutoSchema:
            meta = type('Meta', (object,), dict(
                {'table': self.table, 'include_fk': True, 'dump_only': (self.name_id,)},
                **self.schema_meta))
            self.Schema = type(
                self.name.title() + 'Schema', (SQLAlchemyAutoSchema,),
                dict({'Meta': meta}))

        # Setup sorting
        self.sorting = dict(
            (isinstance(n, sa.Column) and n.name or n, prop)
            for (n, prop) in self.sorting.items())


class SAEndpoint(Endpoint):
    """Support SQLAlchemy Core."""

    meta: SAEndpointOpts
    meta_class: t.Type[SAEndpointOpts] = SAEndpointOpts

    class Meta:
        """Tune sqlalchemy endpoints."""

        filters_cls = SAFilters

        # Sqlalchemy options
        table = None
        table_pk = None
        database = None

        Schema = SQLAlchemyAutoSchema

    async def prepare_collection(self, request: muffin.Request) -> sa.sql.Select:
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        return self.meta.table.select()

    async def paginate(self, request: muffin.Request, *, limit: int = 0,
                       offset: int = 0) -> t.Tuple[sa.sql.Select, int]:
        """Paginate the collection."""
        qs = sa.select([sa.func.count()]).select_from(self.collection.order_by(None))
        total = await self.meta.database.fetch_val(qs)
        return self.collection.offset(offset).limit(limit), total

    async def get(self, request, *, resource=None) -> JSONType:
        """Get resource or collection of resources."""
        if resource is not None and resource != '':
            return await self.dump(request, resource, many=False)

        rows = await self.meta.database.fetch_all(self.collection)
        return await self.dump(request, rows, many=True)

    async def prepare_resource(self, request: muffin.Request) -> t.Optional[dict]:
        """Load a resource."""
        pk = request['path_params'].get(self.meta.name_id)
        if not pk:
            return None

        qs = self.collection.where(self.meta.table_pk == pk)
        resource = await self.meta.database.fetch_one(qs)
        if resource is None:
            raise APIError.NOT_FOUND('Resource not found')
        return dict(resource)

    async def get_schema(self, request: muffin.Request, resource=None) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        return self.meta.Schema(
            instance=resource,
            only=request.url.query.get('schema_only'),
            exclude=request.url.query.get('schema_exclude', ()),
        )

    async def save(self, request: muffin.Request,  # type: ignore
                   resource: t.Union[dict, t.List[dict]]):
        """Save the given resource.

        Supports batch saving.
        """
        resources = resource if isinstance(resource, t.Sequence) else [resource]
        for res in resources:
            if res.get(self.meta.table_pk.name):
                update = self.meta.table.update().where(
                    self.meta.table_pk == res[self.meta.table_pk.name])
                await self.meta.database.execute(update, res)

            else:
                insert = self.meta.table.insert()
                res[self.meta.table_pk.name] = await self.meta.database.execute(insert, res)

        return resource

    async def remove(self, request: muffin.Request, *, resource: dict = None):
        """Remove the given resource."""
        pks = [resource[self.meta.table_pk.name]] if resource else await request.data()
        if not pks:
            raise APIError.NOT_FOUND()

        delete = self.meta.table.delete(self.meta.table_pk.in_(pks))
        await self.meta.database.execute(delete)

    delete = remove  # noqa

    async def sort(self, request: muffin.Request,
                   *sorting: t.Tuple[str, bool], **options) -> sa.sql.Select:
        """Sort the current collection."""
        order_by = []
        for name, desc in sorting:
            column = self.meta.table.c.get(name)
            if column is None:
                continue

            if desc:
                column = column.desc()  # type: ignore

            order_by.append(column)

        if order_by:
            return self.collection.order_by(*order_by)

        return self.collection
