"""SQLAlchemy Core support."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import marshmallow as ma
import sqlalchemy as sa
from marshmallow_sqlalchemy import ModelConverter
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema as BaseSQLAlchemyAutoSchema

from muffin_rest.errors import APIError
from muffin_rest.handler import RESTHandler, RESTOptions
from muffin_rest.sqlalchemy.filters import SAFilters
from muffin_rest.sqlalchemy.sorting import SASorting

if TYPE_CHECKING:
    from muffin import Request
    from muffin_databases import Plugin as Database


from .types import TVResource

ModelConverter._get_field_name = lambda _, prop_or_column: str(prop_or_column.key)  # type: ignore[assignment]


class SQLAlchemyAutoSchema(BaseSQLAlchemyAutoSchema):
    """Allow partial updates for tables."""

    @ma.pre_load
    def fill_defaults(self, data, *, partial=False, **_):
        """Insert default params for SQLAlchemy because databases don't.

        https://github.com/encode/databases/issues/72
        """
        cols_to_fields = {f.attribute or f.name: f for f in self.declared_fields.values()}
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
                        value,
                        field.attribute or field.name,
                        None,
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

    filters_cls: type[SAFilters] = SAFilters
    sorting_cls: type[SASorting] = SASorting

    # Schema auto generation params
    Schema: type[SQLAlchemyAutoSchema]
    schema_base: type[SQLAlchemyAutoSchema] = SQLAlchemyAutoSchema

    table: sa.Table
    table_pk: sa.Column
    database: Database

    base_property = "table"

    def setup(self, cls):
        """Prepare meta options."""
        if self.database is None:
            raise ValueError("'SARESTHandler.Meta.database' is required")

        self.name = self.name or self.table.name
        self.table_pk = getattr(self, "table_pk", None) or self.table.c.id

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
                    "dump_only": (self.table_pk.name,),
                },
                **self.schema_meta,
            ),
        )


class SARESTHandler(RESTHandler[TVResource]):
    """Support SQLAlchemy Core."""

    meta: SARESTOptions
    meta_class: type[SARESTOptions] = SARESTOptions
    collection: sa.sql.Select

    async def prepare_collection(self, _: Request) -> sa.sql.Select:
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        return self.meta.table.select()

    async def paginate(
        self,
        _: Request,
        *,
        limit: int = 0,
        offset: int = 0,
    ) -> tuple[sa.sql.Select, int | None]:
        """Paginate the collection."""
        sqs = self.collection.order_by(None).subquery()
        qs = sa.select(sa.func.count()).select_from(sqs)
        total = None
        if self.meta.limit_total:
            total = await self.meta.database.fetch_val(qs)
        return self.collection.offset(offset).limit(limit), total

    async def get(self, request, *, resource: TVResource | None = None) -> Any:
        """Get resource or collection of resources."""
        if resource:
            return await self.dump(request, resource)

        rows = await self.meta.database.fetch_all(self.collection)
        return await self.dump(request, rows, many=True)

    async def prepare_resource(self, request: Request) -> TVResource | None:
        """Load a resource."""
        pk = request["path_params"].get("pk")
        if not pk:
            return None

        qs = self.collection.where(self.meta.table_pk == pk)
        resource = await self.meta.database.fetch_one(qs)
        if resource is None:
            raise APIError.NOT_FOUND("Resource not found")
        return cast("TVResource", dict(resource))

    def get_schema(
        self, request: Request, *, resource: TVResource | None = None, **schema_options
    ) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        return super().get_schema(request, instance=resource, **schema_options)

    async def save(self, request: Request, resource: TVResource, *, update=False):
        """Save the given resource."""
        meta = self.meta
        insert_query = meta.table.insert()
        table_pk = cast("sa.Column", meta.table_pk)
        if update:
            update_query = self.meta.table.update().where(table_pk == resource[table_pk.name])  # type: ignore[call-overload]
            await meta.database.execute(update_query, resource)

        else:
            resource[table_pk.name] = await meta.database.execute(insert_query, resource)  # type: ignore[call-overload]

        return resource

    async def remove(self, request: Request, resource: TVResource | None = None):
        """Remove the given resource."""
        table_pk = cast("sa.Column", self.meta.table_pk)
        pks = [resource[table_pk.name]] if resource else await request.data()
        if not pks:
            raise APIError.NOT_FOUND()

        delete = self.meta.table.delete().where(table_pk.in_(cast("list[Any]", pks)))
        await self.meta.database.execute(delete)

    delete = remove
