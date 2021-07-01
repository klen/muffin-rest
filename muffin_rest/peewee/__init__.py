"""Support for Peewee ORM (https://github.com/coleifer/peewee)."""

from __future__ import annotations

import typing as t

import marshmallow as ma
import muffin
import peewee as pw
from apispec.ext.marshmallow import MarshmallowPlugin
from marshmallow_peewee import ModelSchema, ForeignKey

from ..handler import RESTBase, RESTOptions
from ..errors import APIError

from .openapi import PeeweeOpenAPIMixin
from .filters import PWFilters
from .sorting import PWSorting


# XXX: Patch apispec.MarshmallowPlugin to support ForeignKeyField
MarshmallowPlugin.Converter.field_mapping[ForeignKey] = ("integer", None)


class PWRESTOptions(RESTOptions):
    """Support Peewee."""

    # Base filters class
    filters_cls: t.Type[PWFilters] = PWFilters

    # Base sorting class
    sorting_cls: t.Type[PWSorting] = PWSorting

    # Schema auto generation params
    schema_base: t.Type[ModelSchema] = ModelSchema

    if t.TYPE_CHECKING:
        model: pw.Model
        model_pk: pw.Field
        Schema: t.Type[ModelSchema]

    def setup(self, cls):
        """Prepare meta options."""
        if not self.model:
            raise ValueError("'PWRESTHandler.Meta.model' is required")

        self.model_pk = self.model_pk or self.model._meta.primary_key

        self.name = self.name or self.model._meta.table_name
        self.name_id = self.name_id or self.model_pk.name

        super(PWRESTOptions, self).setup(cls)

    def setup_schema_meta(self, cls):
        """Prepare a schema."""
        return type('Meta', (object,), dict(
            {'unknown': self.schema_unknown, 'model': self.model}, **self.schema_meta))


class PWRESTBase(RESTBase):
    """Support Peeweee."""

    collection: pw.Query
    resource: pw.Model
    meta: PWRESTOptions
    meta_class: t.Type[PWRESTOptions] = PWRESTOptions

    class Meta:
        """Tune the handler."""

        abc: bool = True

        # Peewee options
        model = None
        model_pk = None

    async def prepare_collection(self, request: muffin.Request) -> pw.Query:
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        return self.meta.model.select()

    async def prepare_resource(self, request: muffin.Request) -> t.Optional[pw.Model]:
        """Load a resource."""
        pk = request['path_params'].get(self.meta.name_id)
        if not pk:
            return None

        try:
            return self.collection.where(self.meta.model_pk == pk).get()
        except self.meta.model.DoesNotExist:
            raise APIError.NOT_FOUND('Resource not found')

    async def paginate(self, request: muffin.Request, *, limit: int = 0,
                       offset: int = 0) -> t.Tuple[pw.Query, int]:
        """Paginate the collection."""
        cqs = self.collection.order_by()
        if cqs._group_by:
            cqs._select = cqs._group_by
        return self.collection.offset(offset).limit(limit), cqs.count()

    async def save(self, request: muffin.Request,  # type: ignore
                   resource: t.Union[pw.Model, t.List[pw.Model]]):
        """Save the given resource.

        Supports batch saving.
        """
        for obj in (resource if isinstance(resource, list) else [resource]):
            obj.save()
        return resource

    async def remove(self, request: muffin.Request, *, resource: pw.Model = None):
        """Remove the given resource."""
        if resource:
            resources = [resource]

        else:
            data = await request.data()
            if not data:
                return
            resources = list(self.collection.where(self.meta.model_pk << data))

        if not resources:
            raise APIError.NOT_FOUND()

        for resource in resources:
            resource.delete_instance()

    delete = remove  # noqa

    async def get_schema(self, request: muffin.Request, resource=None) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        return self.meta.Schema(
            instance=resource,
            only=request.url.query.get('schema_only'),
            exclude=request.url.query.get('schema_exclude', ()),
        ) if self.meta.Schema else None


class PWRESTHandler(PWRESTBase, PeeweeOpenAPIMixin):  # type: ignore
    """Support peewee."""

    class Meta:
        """Tune the handler."""

        abc: bool = True
