"""Support for Peewee ORM (https://github.com/coleifer/peewee)."""

from __future__ import annotations

from typing import Generic, Optional, Tuple, Type, TypeVar, cast

import marshmallow as ma
import muffin
import peewee as pw
from apispec.ext.marshmallow import MarshmallowPlugin
from marshmallow_peewee import ForeignKey, ModelSchema
from muffin.typing import JSONType
from peewee_aio import Manager, Model

from muffin_rest.errors import APIError
from muffin_rest.handler import RESTBase, RESTOptions
from muffin_rest.peewee.filters import PWFilters
from muffin_rest.peewee.openapi import PeeweeOpenAPIMixin
from muffin_rest.peewee.sorting import PWSorting

# XXX: Patch apispec.MarshmallowPlugin to support ForeignKeyField
MarshmallowPlugin.Converter.field_mapping[ForeignKey] = ("integer", None)

TVModel = TypeVar("TVModel", bound=pw.Model)


class PWRESTOptions(RESTOptions):
    """Support Peewee."""

    model: Type[pw.Model]
    model_pk: Optional[pw.Field] = None

    manager: Manager

    # Base filters class
    filters_cls: Type[PWFilters] = PWFilters

    # Base sorting class
    sorting_cls: Type[PWSorting] = PWSorting

    Schema: Type[ModelSchema]

    # Schema auto generation params
    schema_base: Type[ModelSchema] = ModelSchema

    # Recursive delete
    delete_recursive = False

    base_property: str = "model"

    def setup(self, cls):
        """Prepare meta options."""
        self.name = self.name or self.model._meta.table_name.lower()
        self.model_pk = self.model_pk or self.model._meta.primary_key
        manager = getattr(self, "manager", getattr(self.model, "_manager", None))
        if manager is None:
            raise RuntimeError("Peewee-AIO ORM Manager is not available")

        self.manager = manager

        super().setup(cls)

    def setup_schema_meta(self, _):
        """Prepare a schema."""
        return type(
            "Meta",
            (object,),
            dict(
                {"unknown": self.schema_unknown, "model": self.model},
                **self.schema_meta,
            ),
        )


class PWRESTBase(Generic[TVModel], RESTBase):
    """Support Peeweee."""

    collection: pw.Query
    resource: pw.Model
    meta: PWRESTOptions
    meta_class: Type[PWRESTOptions] = PWRESTOptions

    # NOTE: there is not a default sorting for peewee (conflict with muffin-admin)
    async def prepare_collection(self, _: muffin.Request) -> pw.Query:
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        return self.meta.model.select()

    async def prepare_resource(self, request: muffin.Request) -> Optional[TVModel]:
        """Load a resource."""
        pk = request["path_params"].get(self.meta.name_id)
        if not pk:
            return None

        meta = self.meta

        try:
            resource = await meta.manager.fetchone(
                self.collection.where(meta.model_pk == pk)
            )
        except Exception:
            resource = None

        if resource is None:
            raise APIError.NOT_FOUND("Resource not found")

        return resource

    async def paginate(
        self, _: muffin.Request, *, limit: int = 0, offset: int = 0
    ) -> Tuple[pw.Query, int]:
        """Paginate the collection."""
        cqs: pw.Select = self.collection.order_by()  # type: ignore
        if cqs._group_by:
            cqs._returning = cqs._group_by
        count = await self.meta.manager.count(cqs)
        return self.collection.offset(offset).limit(limit), count  # type: ignore

    async def get(self, request, *, resource: Optional[TVModel] = None) -> JSONType:
        """Get resource or collection of resources."""
        if resource is not None and resource != "":
            return await self.dump(request, resource=resource)

        resources = await self.meta.manager.fetchall(self.collection)
        return await self.dump(request, data=resources, many=True)

    async def save(self, _: muffin.Request, resource: TVModel) -> TVModel:
        """Save the given resource."""
        meta = self.meta
        if issubclass(meta.model, Model):
            await resource.save()
        else:
            await meta.manager.save(resource)

        return resource

    async def remove(self, request: muffin.Request, resource: TVModel):
        """Remove the given resource."""
        meta = self.meta
        if resource:
            resources = [resource]

        else:
            data = await request.data()
            if not data:
                return

            model_pk = cast(pw.Field, meta.model_pk)
            resources = await meta.manager.fetchall(
                self.collection.where(model_pk << data)
            )

        if not resources:
            raise APIError.NOT_FOUND()

        delete_instance = meta.manager.delete_instance
        if issubclass(meta.model, Model):
            delete_instance = lambda m: m.delete_instance(recursive=meta.delete_recursive)  # type: ignore  # noqa

        for res in resources:
            await delete_instance(res)

    delete = remove  # type: ignore

    async def get_schema(
        self, request: muffin.Request, resource: Optional[TVModel] = None, **_
    ) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        return self.meta.Schema(
            instance=resource,
            only=request.url.query.get("schema_only"),
            exclude=request.url.query.get("schema_exclude", ()),
        )


class PWRESTHandler(PWRESTBase[TVModel], PeeweeOpenAPIMixin):  # type: ignore
    """Support peewee."""

    pass
