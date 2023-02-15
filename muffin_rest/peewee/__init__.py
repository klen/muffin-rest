"""Support for Peewee ORM (https://github.com/coleifer/peewee)."""

from __future__ import annotations

from typing import Optional, Tuple, Type, TypeVar, cast

import marshmallow as ma
import peewee as pw
from apispec.ext.marshmallow import MarshmallowPlugin
from marshmallow_peewee import ForeignKey
from muffin import Request
from muffin.typing import JSONType
from peewee_aio import Model

from muffin_rest.errors import APIError
from muffin_rest.handler import RESTBase
from muffin_rest.peewee.openapi import PeeweeOpenAPIMixin

from .options import PWRESTOptions

# XXX: Patch apispec.MarshmallowPlugin to support ForeignKeyField
MarshmallowPlugin.Converter.field_mapping[ForeignKey] = ("integer", None)

TVModel = TypeVar("TVModel", bound=pw.Model)


class PWRESTHandler(RESTBase[TVModel], PeeweeOpenAPIMixin):
    """Support Peeweee."""

    collection: pw.Query
    resource: pw.Model
    meta: PWRESTOptions
    meta_class: Type[PWRESTOptions] = PWRESTOptions

    # NOTE: there is not a default sorting for peewee (conflict with muffin-admin)
    async def prepare_collection(self, _: Request) -> pw.Query:
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        return self.meta.model.select()

    async def prepare_resource(self, request: Request) -> Optional[TVModel]:
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
        self, _: Request, *, limit: int = 0, offset: int = 0
    ) -> Tuple[pw.Query, int]:
        """Paginate the collection."""
        cqs: pw.Select = self.collection.order_by()
        if cqs._group_by:
            cqs._returning = cqs._group_by
        count = await self.meta.manager.count(cqs)
        return self.collection.offset(offset).limit(limit), count

    async def get(self, request, *, resource: Optional[TVModel] = None) -> JSONType:
        """Get resource or collection of resources."""
        if resource is not None and resource != "":
            return await self.dump(request, resource=resource)

        resources = await self.meta.manager.fetchall(self.collection)
        return await self.dump(request, data=resources, many=True)

    async def save(self, _: Request, resource: TVModel) -> TVModel:
        """Save the given resource."""
        meta = self.meta
        if issubclass(meta.model, Model):
            await resource.save()
        else:
            await meta.manager.save(resource)

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

            model_pk = cast(pw.Field, meta.model_pk)
            resources = await meta.manager.fetchall(
                self.collection.where(model_pk << data)
            )

        if not resources:
            raise APIError.NOT_FOUND()

        is_aiomodel = issubclass(meta.model, Model)
        if is_aiomodel:
            for res in resources:
                await res.delete_instance(recursive=meta.delete_recursive)
        else:
            for res in resources:
                await meta.manager.delete_instance(res, recursive=meta.delete_recursive)

    delete = remove

    async def get_schema(
        self, request: Request, resource: Optional[TVModel] = None, **_
    ) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        return self.meta.Schema(
            instance=resource,
            only=request.url.query.get("schema_only"),
            exclude=request.url.query.get("schema_exclude", ()),
        )
