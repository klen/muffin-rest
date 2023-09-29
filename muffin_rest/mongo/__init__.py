"""Mongo DB support."""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple, Type, cast

import bson
from bson.errors import InvalidId

from muffin_rest.errors import APIError
from muffin_rest.handler import RESTHandler, RESTOptions
from muffin_rest.mongo.filters import MongoFilters
from muffin_rest.mongo.schema import MongoSchema
from muffin_rest.mongo.sorting import MongoSorting
from muffin_rest.mongo.utils import MongoChain

from .types import TVResource

if TYPE_CHECKING:
    import marshmallow as ma
    from motor import motor_asyncio as motor
    from muffin import Request


class MongoRESTOptions(RESTOptions):
    """Support Mongo DB."""

    filters_cls: Type[MongoFilters] = MongoFilters
    sorting_cls: Type[MongoSorting] = MongoSorting
    schema_base: Type[MongoSchema] = MongoSchema

    aggregate: Optional[List] = None  # Support aggregation. Set to pipeline.
    collection_id: str = "_id"
    collection: motor.AsyncIOMotorCollection

    base_property: str = "collection"

    Schema: Type[MongoSchema]

    def setup(self, cls):
        """Prepare meta options."""
        if self.collection is None:
            raise RuntimeError("MongoResthandler.Meta.collection is required")
        self.name = getattr(self, "name", self.collection.name.lower())
        self.name = self.name or self.collection.name.lower()
        super().setup(cls)


class MongoRESTHandler(RESTHandler[TVResource]):
    """Support Mongo DB."""

    meta: MongoRESTOptions
    meta_class: Type[MongoRESTOptions] = MongoRESTOptions

    async def prepare_collection(self, _: Request) -> MongoChain:
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        return MongoChain(self.meta.collection)

    async def paginate(
        self, _: Request, *, limit: int = 0, offset: int = 0
    ) -> Tuple[motor.AsyncIOMotorCursor, Optional[int]]:
        """Paginate collection."""
        if self.meta.aggregate:
            pipeline_all = [*self.meta.aggregate, {"$skip": offset}, {"$limit": limit}]
            pipeline_num = [
                *self.meta.aggregate,
                {"$group": {self.meta.collection_id: None, "total": {"$sum": 1}}},
            ]
            counts = list(self.collection.aggregate(pipeline_num))
            return (
                self.collection.aggregate(pipeline_all),
                counts and counts[0]["total"] or 0,  # type: ignore[]
            )
        total = None
        if self.meta.limit_total:
            total = await self.collection.count()
        return self.collection.skip(offset).limit(limit), total

    async def get(self, request, *, resource: Optional[TVResource] = None):
        """Get resource or collection of resources."""
        if resource:
            return await self.dump(request, resource)

        docs = await self.collection.to_list(None)
        return await self.dump(request, docs, many=True)

    async def prepare_resource(self, request: Request) -> Optional[TVResource]:
        """Load a resource."""
        pk = request["path_params"].get(self.meta.name_id)
        if not pk:
            return None

        try:
            return await self.collection.find_one(
                {self.meta.collection_id: bson.ObjectId(pk)},
            )
        except InvalidId as exc:
            raise APIError.NOT_FOUND() from exc

    def get_schema(
        self, request: Request, resource: Optional[TVResource] = None, **schema_options
    ) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        return super().get_schema(request, instance=resource, **schema_options)

    async def save(self, _: Request, resource: TVResource, *, update=False) -> TVResource:
        """Save the given resource."""
        meta = self.meta
        collection_id = meta.collection_id
        if update:
            await self.collection.replace_one({collection_id: resource[collection_id]}, resource)

        else:
            updated = await meta.collection.insert_one(resource)
            resource[collection_id] = updated.inserted_id

        return resource

    async def delete(self, request: Request, resource: Optional[TVResource] = None):
        """Remove the given resource(s)."""
        meta = self.meta
        oids = [resource[meta.collection_id]] if resource else cast(List[str], await request.data())
        if not oids:
            raise APIError.NOT_FOUND()

        if not isinstance(oids, list):
            raise APIError.BAD_REQUEST()

        oids = [bson.ObjectId(idx) for idx in oids]
        await meta.collection.delete_many({meta.collection_id: {"$in": oids}})
