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
from .filters import SAFilters
from .sorting import SASorting


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


class SARESTOptions(RESTOptions):
    """Support SQLAlchemy Core."""

    filters_cls: t.Type[SAFilters] = SAFilters
    sorting_cls: t.Type[SASorting] = SASorting

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
