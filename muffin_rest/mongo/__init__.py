"""Mongo DB support."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type, TypeVar

import bson
import marshmallow as ma
from bson.errors import InvalidId
from motor import motor_asyncio as motor
from muffin import Request

from muffin_rest.errors import APIError
from muffin_rest.handler import RESTHandler, RESTOptions
from muffin_rest.mongo.filters import MongoFilters
from muffin_rest.mongo.schema import MongoSchema
from muffin_rest.mongo.sorting import MongoSorting
from muffin_rest.mongo.utils import MongoChain

TResource = Dict[str, Any]
TVResource = TypeVar("TVResource", bound=TResource)


class MongoRESTOptions(RESTOptions):
    """Support Mongo DB."""

    filters_cls: Type[MongoFilters] = MongoFilters
    sorting_cls: Type[MongoSorting] = MongoSorting
    schema_base: Type[MongoSchema] = MongoSchema

    aggregate: Optional[List] = None  # Support aggregation. Set to pipeline.
    collection_id: str = "_id"
    collection: Optional[motor.AsyncIOMotorCollection] = None

    base_property: str = "collection"

    if TYPE_CHECKING:
        Schema: Type[MongoSchema]

    def setup(self, cls):
        """Prepare meta options."""
        if self.collection is None:
            raise RuntimeError("MongoResthandler.Meta.collection is required")
        self.name = self.name or self.collection.name.lower()
        super().setup(cls)


class MongoRESTHandler(RESTHandler):
    """Support Mongo DB."""

    meta: MongoRESTOptions
    meta_class: Type[MongoRESTOptions] = MongoRESTOptions

    async def prepare_collection(self, _: Request) -> MongoChain:
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        return MongoChain(self.meta.collection)

    async def paginate(
        self, _: Request, *, limit: int = 0, offset: int = 0
    ) -> Tuple[motor.AsyncIOMotorCursor, int]:
        """Paginate collection."""
        if self.meta.aggregate:
            pipeline_all = self.meta.aggregate + [{"$skip": offset}, {"$limit": limit}]
            pipeline_num = self.meta.aggregate + [
                {"$group": {self.meta.collection_id: None, "total": {"$sum": 1}}}
            ]
            counts = list(self.collection.aggregate(pipeline_num))
            return (
                self.collection.aggregate(pipeline_all),
                counts and counts[0]["total"] or 0,
            )
        total = await self.collection.count()
        return self.collection.skip(offset).limit(limit), total

    async def get(self, request, *, resource: Optional[TVResource] = None):
        """Get resource or collection of resources."""
        if resource is not None and resource != "":
            return await self.dump(request, resource=resource)

        docs = await self.collection.to_list(None)
        return await self.dump(request, data=docs, many=True)

    async def prepare_resource(self, request: Request) -> Optional[TVResource]:
        """Load a resource."""
        pk = request["path_params"].get(self.meta.name_id)
        if not pk:
            return None

        try:
            return await self.collection.find_one(
                {self.meta.collection_id: bson.ObjectId(pk)}
            )
        except InvalidId as exc:
            raise APIError.NOT_FOUND() from exc

    async def get_schema(
        self, request: Request, resource: Optional[TVResource] = None, **_
    ) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        return self.meta.Schema(
            instance=resource,
            only=request.url.query.get("schema_only"),
            exclude=request.url.query.get("schema_exclude", ()),
        )

    async def save(self, _: Request, resource: TVResource) -> TVResource:
        """Save the given resource."""
        if resource.get(self.meta.collection_id):
            await self.collection.replace_one(
                {self.meta.collection_id: resource[self.meta.collection_id]}, resource
            )

        else:
            res = await self.meta.collection.insert_one(resource)  # type: ignore
            resource[self.meta.collection_id] = res.inserted_id

        return resource

    async def remove(self, request: Request, resource: Optional[TVResource] = None):
        """Remove the given resource(s)."""
        oids = [resource[self.meta.collection_id]] if resource else await request.data()
        if not oids:
            raise APIError.NOT_FOUND()

        if not isinstance(oids, list):
            raise APIError.BAD_REQUEST()

        oids = [bson.ObjectId(idx) for idx in oids]
        await self.meta.collection.delete_many(  # type: ignore
            {self.meta.collection_id: {"$in": oids}}
        )

    delete = remove  # noqa
