"""Support for Peewee ORM (https://github.com/coleifer/peewee)."""

from __future__ import annotations

import typing as t

import marshmallow as ma
import muffin
import peewee as pw
from apispec.ext.marshmallow import MarshmallowPlugin
from marshmallow_peewee import ForeignKey, ModelSchema
from muffin.typing import JSONType
from peewee_aio import Manager, Model

from ..errors import APIError
from ..handler import RESTBase, RESTOptions
from .filters import PWFilters
from .openapi import PeeweeOpenAPIMixin
from .sorting import PWSorting

# XXX: Patch apispec.MarshmallowPlugin to support ForeignKeyField
MarshmallowPlugin.Converter.field_mapping[ForeignKey] = ("integer", None)


class PWRESTOptions(RESTOptions):
    """Support Peewee."""

    model: t.Type[pw.Model]
    model_pk: t.Optional[pw.Field] = None

    manager: Manager

    # Base filters class
    filters_cls: t.Type[PWFilters] = PWFilters

    # Base sorting class
    sorting_cls: t.Type[PWSorting] = PWSorting

    Schema: t.Type[ModelSchema]

    # Schema auto generation params
    schema_base: t.Type[ModelSchema] = ModelSchema

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

        super(PWRESTOptions, self).setup(cls)

    def setup_schema_meta(self, _):
        """Prepare a schema."""
        return type(
            "Meta",
            (object,),
            dict(
                {"unknown": self.schema_unknown, "model": self.model},
                **self.schema_meta
            ),
        )


class PWRESTBase(RESTBase):
    """Support Peeweee."""

    collection: pw.Query
    resource: pw.Model
    meta: PWRESTOptions
    meta_class: t.Type[PWRESTOptions] = PWRESTOptions

    async def prepare_collection(self, _: muffin.Request) -> pw.Query:
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        return self.meta.model.select()

    async def prepare_resource(self, request: muffin.Request) -> t.Optional[pw.Model]:
        """Load a resource."""
        pk = request["path_params"].get(self.meta.name_id)
        if not pk:
            return None

        meta = self.meta

        resource = await meta.manager.fetchone(
            self.collection.where(meta.model_pk == pk)
        )
        if resource is None:
            raise APIError.NOT_FOUND("Resource not found")
        return resource

    async def paginate(
        self, _: muffin.Request, *, limit: int = 0, offset: int = 0
    ) -> t.Tuple[pw.Query, int]:
        """Paginate the collection."""
        cqs: pw.Select = self.collection.order_by()  # type: ignore
        if cqs._group_by:
            cqs._returning = cqs._group_by
        count = await self.meta.manager.count(cqs)
        return self.collection.offset(offset).limit(limit), count  # type: ignore

    async def get(self, request, *, resource=None) -> JSONType:
        """Get resource or collection of resources."""
        if resource is not None and resource != "":
            return await self.dump(request, resource, many=False)

        resources = await self.meta.manager.fetchall(self.collection)
        return await self.dump(request, resources, many=True)

    async def save(
        self,
        _: muffin.Request,  # type: ignore
        resource: t.Union[pw.Model, t.List[pw.Model]],
    ):
        """Save the given resource.

        Supports batch saving.
        """
        meta = self.meta
        save = meta.manager.save
        if issubclass(meta.model, Model):
            save = lambda m: m.save()  # type: ignore  # noqa

        for obj in resource if isinstance(resource, list) else [resource]:
            await save(obj)

        return resource

    async def remove(self, request: muffin.Request, *, resource: pw.Model = None):
        """Remove the given resource."""
        meta = self.meta
        if resource:
            resources = [resource]

        else:
            data = await request.data()
            if not data:
                return

            model_pk = t.cast(pw.Field, meta.model_pk)
            resources = await meta.manager.fetchall(
                self.collection.where(model_pk << data)
            )

        if not resources:
            raise APIError.NOT_FOUND()

        delete_instance = meta.manager.delete_instance
        if issubclass(meta.model, Model):
            delete_instance = lambda m: m.delete_instance(recursive=meta.delete_recursive)  # type: ignore  # noqa

        for resource in resources:
            await delete_instance(resource)

    delete = remove  # noqa

    async def get_schema(
        self, request: muffin.Request, resource=None, **_
    ) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        return self.meta.Schema(
            instance=resource,
            only=request.url.query.get("schema_only"),
            exclude=request.url.query.get("schema_exclude", ()),
        )


class PWRESTHandler(PWRESTBase, PeeweeOpenAPIMixin):  # type: ignore
    """Support peewee."""

    pass
