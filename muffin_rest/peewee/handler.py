"""Support for Peewee ORM (https://github.com/coleifer/peewee)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast, overload

import marshmallow as ma
from apispec.ext.marshmallow import MarshmallowPlugin
from marshmallow_peewee import ForeignKey
from peewee_aio.model import AIOModel, AIOModelSelect

from muffin_rest.errors import APIError
from muffin_rest.handler import RESTBase
from muffin_rest.peewee.openapi import PeeweeOpenAPIMixin

from .options import PWRESTOptions
from .schemas import EnumField
from .types import TVModel

if TYPE_CHECKING:
    import peewee as pw
    from muffin import Request
    from peewee_aio.types import TVAIOModel


# TODO: Patch apispec.MarshmallowPlugin to support ForeignKeyField
MarshmallowPlugin.Converter.field_mapping[ForeignKey] = ("integer", None)

assert issubclass(EnumField, ma.fields.Field)  # just register EnumField


class PWRESTBase(RESTBase[TVModel], PeeweeOpenAPIMixin):
    """Support Peeweee."""

    if TYPE_CHECKING:
        resource: TVModel
        collection: AIOModelSelect | pw.ModelSelect

    meta: PWRESTOptions
    meta_class: type[PWRESTOptions] = PWRESTOptions

    @overload
    async def prepare_collection(
        self: PWRESTBase[TVAIOModel],
        _: Request,
    ) -> AIOModelSelect[TVAIOModel]: ...

    @overload
    async def prepare_collection(
        self: PWRESTBase[pw.Model],
        _: Request,
    ) -> pw.ModelSelect: ...

    # NOTE: there is not a default sorting for peewee (conflict with muffin-admin)
    async def prepare_collection(self, _: Request):  # type: ignore[override]
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        return self.meta.model.select()

    async def prepare_resource(self, request: Request) -> TVModel | None:
        """Load a resource."""
        pk = request["path_params"].get("pk")
        if not pk:
            return None

        meta = self.meta

        try:
            resource = await meta.manager.fetchone(
                self.collection.where(meta.model_pk == pk),
            )
        except Exception:  # noqa: BLE001
            resource = None

        if resource is None:
            raise APIError.NOT_FOUND("Resource not found")

        return resource

    @overload
    async def paginate(
        self: PWRESTBase[TVAIOModel], _: Request, *, limit: int = 0, offset: int = 0
    ) -> tuple[AIOModelSelect[TVAIOModel], int | None]: ...

    @overload
    async def paginate(
        self: PWRESTBase[pw.Model], _: Request, *, limit: int = 0, offset: int = 0
    ) -> tuple[pw.ModelSelect, int | None]: ...

    async def paginate(self, _: Request, *, limit: int = 0, offset: int = 0):  # type: ignore[override]
        """Paginate the collection."""
        if self.meta.limit_total:
            cqs = cast("pw.ModelSelect", self.collection.order_by())
            if cqs._group_by:  # type: ignore[misc]
                cqs._returning = cqs._group_by  # type: ignore[misc]
                cqs._having = None  # type: ignore[misc]

            count = await self.meta.manager.count(cqs)

        else:
            count = None

        return self.collection.offset(offset).limit(limit), count

    async def get(self, request, *, resource: TVModel | None = None) -> Any:
        """Get resource or collection of resources."""
        if resource:
            return await self.dump(request, resource)

        resources = await self.meta.manager.fetchall(self.collection)
        return await self.dump(request, resources, many=True)

    async def save(self, request: Request, resource: TVModel, *, update=False):
        """Save the given resource."""
        meta = self.meta
        manager = meta.manager
        if issubclass(meta.model, AIOModel):
            await resource.save(force_insert=not update)
        else:
            await manager.save(resource, force_insert=not update)

        return resource

    async def remove(self, request: Request, resource: TVModel | None = None):
        """Remove the given resource."""
        meta = self.meta
        if resource:
            resources = [resource]

        else:
            data = await request.data()
            if not data:
                return

            model_pk = cast("pw.Field", meta.model_pk)
            resources = await meta.manager.fetchall(self.collection.where(model_pk << data))  # type: ignore[]

        if not resources:
            raise APIError.NOT_FOUND()

        is_aiomodel = issubclass(meta.model, AIOModel)
        if is_aiomodel:
            for res in resources:
                await res.delete_instance(recursive=meta.delete_recursive)
        else:
            for res in resources:
                await meta.manager.delete_instance(res, recursive=meta.delete_recursive)

        return resource.get_id() if resource else [r.get_id() for r in resources]

    async def delete(self, request: Request, resource: TVModel | None = None):  # type: ignore[override]
        return await self.remove(request, resource)

    def get_schema(
        self, request: Request, *, resource: TVModel | None = None, **schema_options
    ) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        return super().get_schema(request, instance=resource, **schema_options)


class PWRESTHandler(PWRESTBase[TVModel], PeeweeOpenAPIMixin):
    meta: PWRESTOptions
