"""SQLAlchemy Core support."""

from __future__ import annotations

from typing import Optional, Tuple, Type, cast

import marshmallow as ma
import sqlalchemy as sa
from asgi_tools.types import TJSON
from marshmallow_sqlalchemy import ModelConverter
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema as BaseSQLAlchemyAutoSchema
from muffin import Request
from muffin_databases import Plugin as DB

from muffin_rest.errors import APIError
from muffin_rest.handler import RESTHandler, RESTOptions
from muffin_rest.sqlalchemy.filters import SAFilters
from muffin_rest.sqlalchemy.sorting import SASorting

from .types import TVResource

# XXX: Monkey patch ModelConverter
ModelConverter._get_field_name = lambda _, prop_or_column: str(prop_or_column.key)  # type: ignore


class SQLAlchemyAutoSchema(BaseSQLAlchemyAutoSchema):
    """Allow partial updates for tables."""

    @ma.pre_load
    def fill_defaults(self, data, partial=False, **_):
        """Insert default params for SQLAlchemy because databases don't.

        https://github.com/encode/databases/issues/72
        """
        cols_to_fields = {
            f.attribute or f.name: f for f in self.declared_fields.values()
        }
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

                    data[data_key] = field._serialize(
                        value, field.attribute or field.name, None
                    )

        return data

    @ma.post_load
    def make_instance(self, data, **kwargs):
        """Update a table instance."""
        if self.instance is not None:
            instance = dict(self.instance)
            instance.update(data)
            return instance
        return super().make_instance(data, **kwargs)


class SARESTOptions(RESTOptions):
    """Support SQLAlchemy Core."""

    filters_cls: Type[SAFilters] = SAFilters
    sorting_cls: Type[SASorting] = SASorting

    # Schema auto generation params
    Schema: Type[SQLAlchemyAutoSchema]
    schema_base: Type[SQLAlchemyAutoSchema] = SQLAlchemyAutoSchema

    table: sa.Table
    table_pk: Optional[sa.Column] = None
    database: DB

    base_property = "table"

    def setup(self, cls):
        """Prepare meta options."""
        if self.database is None:
            raise ValueError("'SARESTHandler.Meta.database' is required")

        self.name = self.name or self.table.name
        self.table_pk = self.table_pk or self.table.c.id

        super().setup(cls)

    def setup_schema_meta(self, _):
        """Prepare a schema."""
        return type(
            "Meta",
            (object,),
            dict(
                {
                    "unknown": self.schema_unknown,
                    "table": self.table,
                    "include_fk": True,
                    "dump_only": (self.name_id,),
                },
                **self.schema_meta,
            ),
        )


class SARESTHandler(RESTHandler):
    """Support SQLAlchemy Core."""

    meta: SARESTOptions
    meta_class: Type[SARESTOptions] = SARESTOptions

    async def prepare_collection(self, _: Request) -> sa.sql.Select:
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        return self.meta.table.select()

    async def paginate(
        self, _: Request, *, limit: int = 0, offset: int = 0
    ) -> Tuple[sa.sql.Select, int]:
        """Paginate the collection."""
        qs = sa.select([sa.func.count()]).select_from(
            self.collection.order_by(None).subquery()
        )
        total = await self.meta.database.fetch_val(qs)
        return self.collection.offset(offset).limit(limit), total

    async def get(self, request, *, resource: Optional[TVResource] = None) -> TJSON:
        """Get resource or collection of resources."""
        if resource is not None and resource != "":
            return await self.dump(request, resource=resource)

        rows = await self.meta.database.fetch_all(self.collection)
        return await self.dump(request, data=rows, many=True)

    async def prepare_resource(self, request: Request) -> Optional[TVResource]:
        """Load a resource."""
        pk = request["path_params"].get(self.meta.name_id)
        if not pk:
            return None

        qs = self.collection.where(self.meta.table_pk == pk)
        resource = await self.meta.database.fetch_one(qs)
        if resource is None:
            raise APIError.NOT_FOUND("Resource not found")
        return cast(TVResource, dict(resource))

    async def get_schema(
        self, request: Request, *, resource: Optional[TVResource] = None, **_
    ) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        return self.meta.Schema(
            instance=resource,
            only=request.url.query.get("schema_only"),
            exclude=request.url.query.get("schema_exclude", ()),
        )

    async def save(self, _: Request, resource: TVResource) -> TVResource:
        """Save the given resource."""
        table_pk = cast(sa.Column, self.meta.table_pk)
        if resource.get(table_pk.name):
            update = self.meta.table.update().where(table_pk == resource[table_pk.name])
            await self.meta.database.execute(update, resource)

        else:
            insert = self.meta.table.insert()
            resource[table_pk.name] = await self.meta.database.execute(insert, resource)

        return resource

    async def remove(self, request: Request, resource: Optional[TVResource] = None):
        """Remove the given resource."""
        table_pk = cast(sa.Column, self.meta.table_pk)
        pks = [resource[table_pk.name]] if resource else await request.data()
        if not pks:
            raise APIError.NOT_FOUND()

        delete = self.meta.table.delete(table_pk.in_(pks))
        await self.meta.database.execute(delete)

    delete = remove  # noqa
