"""SQLAlchemy Core support."""

from __future__ import annotations  # py37

import typing as t

import marshmallow as ma
import muffin
import sqlalchemy as sa
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema as BaseSQLAlchemyAutoSchema, ModelConverter
from muffin.typing import JSONType
from muffin_databases import Plugin as DB

from ..handler import RESTHandler, RESTOptions
from ..errors import APIError
from ..filters import Filter, Filters


# XXX: Monkey patch ModelConverter
ModelConverter._get_field_name = lambda s, prop_or_column: str(prop_or_column.key)


class SQLAlchemyAutoSchema(BaseSQLAlchemyAutoSchema):
    """Allow partial updates for tables."""

    @ma.pre_load
    def fill_defaults(self, data, partial=False, **kwargs):
        """Insert default params for SQLAlchemy because databases don't.

        https://github.com/encode/databases/issues/72
        """
        cols_to_fields = {
            f.attribute or f.name: f for f in self.declared_fields.values()}
        if not partial:
            for column in self.opts.table.columns:
                field = cols_to_fields.get(column.name)
                if not field:
                    continue

                data_key = field.data_key or field.name
                if data_key not in data and column.default is not None:
                    value = column.default.arg
                    if callable(value):
                        value = value(column)

                    data[data_key] = field._serialize(value, field.attribute or field.name, None)

        return data

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
    operators['$between'] = lambda c, v: c.between(*v)
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

    def __init__(self, name: str, *, column: sa.Column = None, **kwargs):
        """Support custom model fields."""
        super().__init__(name, **kwargs)
        self.column = column

    def apply(self, collection: sa.sql.Select, *ops: t.Tuple[t.Callable, t.Any],
              handler: SARESTHandler = None, **kwargs) -> sa.sql.Select:
        """Apply the filters to SQLAlchemy Select."""
        column = self.column
        if column is None and handler:
            column = handler.meta.table.c.get(self.field.attribute or self.field.name)

        if ops and column is not None:
            return self.query(collection, column, *ops, **kwargs)

        return collection

    def query(self, select: sa.sql.Select, column: sa.Column, *ops, **kwargs) -> sa.sql.Select:
        """Filter a select."""
        return select.where(*[op(column, val) for op, val in ops])


class SAFilters(Filters):
    """Bind SAfilter class."""

    FILTER_CLASS = SAFilter


class SARESTOptions(RESTOptions):
    """Support SQLAlchemy Core."""

    # Base filters class
    filters_cls: t.Type[SAFilters] = SAFilters

    # Schema auto generation params
    schema_base: t.Type[SQLAlchemyAutoSchema] = SQLAlchemyAutoSchema

    if t.TYPE_CHECKING:
        table: sa.Table
        table_pk: sa.Column
        database: DB
        Schema: t.Type[SQLAlchemyAutoSchema]

    def setup(self, cls):
        """Prepare meta options."""
        if self.table is None:
            raise ValueError("'SARESTHandler.Meta.table' is required")

        if self.database is None:
            raise ValueError("'SARESTHandler.Meta.database' is required")

        self.table_pk = self.table_pk or self.table.c.id

        self.name = self.name or self.table.name
        self.name_id = self.name_id or self.table_pk.name

        super(SARESTOptions, self).setup(cls)

        # Setup sorting
        self.sorting = dict(
            (sort.name, sort) if isinstance(sort, sa.Column) else (
                sort, self.table.columns.get(sort))
            for sort in self.sorting
        )

        sorting_default = []
        for sort in (isinstance(self.sorting_default, t.Sequence) and
                     self.sorting_default or [self.sorting_default]):
            if isinstance(sort, str):
                name, desc = sort.strip('-'), sort.startswith('-')
                sort = self.table.columns.get(name)
                if sort is not None and desc:
                    sort = sort.desc()

            if isinstance(sort, sa.Column):
                sorting_default.append(sort)

        self.sorting_default = sorting_default

    def setup_schema_meta(self, cls):
        """Prepare a schema."""
        return type('Meta', (object,), dict({
            'unknown': self.schema_unknown, 'table': self.table,
            'include_fk': True, 'dump_only': (self.name_id,)
        }, **self.schema_meta))


class SARESTHandler(RESTHandler):
    """Support SQLAlchemy Core."""

    meta: SARESTOptions
    meta_class: t.Type[SARESTOptions] = SARESTOptions

    class Meta:
        """Tune the handler."""

        abc = True

        # Sqlalchemy options
        table = None
        table_pk = None
        database = None

    async def prepare_collection(self, request: muffin.Request) -> sa.sql.Select:
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        qs = self.meta.table.select()
        if self.meta.sorting_default:
            qs = qs.order_by(*self.meta.sorting_default)
        return qs

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
            column = self.meta.sorting.get(name)
            if desc:
                column = column.desc()  # type: ignore

            order_by.append(column)

        return self.collection.order_by(*order_by)
