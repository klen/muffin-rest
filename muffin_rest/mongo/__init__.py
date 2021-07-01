"""Mongo DB support."""

import typing as t

import bson
import marshmallow as ma
import muffin
from motor import motor_asyncio as motor

from ..handler import RESTHandler, RESTOptions
from ..errors import APIError

from .schema import MongoSchema
from .utils import MongoChain
from .filters import MongoFilters
from .sorting import MongoSorting


class MongoRESTOptions(RESTOptions):
    """Support Mongo DB."""

    filters_cls: t.Type[MongoFilters] = MongoFilters
    sorting_cls: t.Type[MongoSorting] = MongoSorting
    schema_base: t.Type[MongoSchema] = MongoSchema

    aggregate: t.Optional[t.List] = None  # Support aggregation. Set to pipeline.
    collection_id: str = '_id'

    if t.TYPE_CHECKING:
        Schema: t.Type[MongoSchema]
        collection: motor.AsyncIOMotorCollection

    def setup(self, cls):
        """Prepare meta options."""
        if not self.collection:
            raise ValueError("'MongoRESTHandler.Meta.collection' is required")

        super(MongoRESTOptions, self).setup(cls)


class MongoRESTHandler(RESTHandler):
    """Support Mongo DB."""

    meta: MongoRESTOptions
    meta_class: t.Type[MongoRESTOptions] = MongoRESTOptions

    class Meta:
        """Tune the handler."""

        abc = True

        # Mongo options
        collection: t.Optional[motor.AsyncIOMotorCollection] = None
        aggregate: t.Optional[t.List] = None  # Support aggregation. Set to pipeline.

    async def prepare_collection(self, request: muffin.Request) -> MongoChain:
        """Initialize Peeewee QuerySet for a binded to the resource model."""
        return MongoChain(self.meta.collection)

    async def paginate(self, request: muffin.Request, *, limit: int = 0,
                       offset: int = 0) -> t.Tuple[motor.AsyncIOMotorCursor, int]:
        """Paginate collection."""
        if self.meta.aggregate:
            pipeline_all = self.meta.aggregate + [{'$skip': offset}, {'$limit': limit}]
            pipeline_num = self.meta.aggregate + [{'$group': {
                self.meta.collection_id: None, 'total': {'$sum': 1}}}]
            counts = list(self.collection.aggregate(pipeline_num))
            return (
                self.collection.aggregate(pipeline_all),
                counts and counts[0]['total'] or 0
            )
        total = await self.collection.count()
        return self.collection.skip(offset).limit(limit), total

    async def get(self, request, *, resource=None):
        """Get resource or collection of resources."""
        if resource is not None and resource != '':
            return await self.dump(request, resource, many=False)

        docs = await self.collection.to_list(None)
        return await self.dump(request, docs, many=True)

    async def prepare_resource(self, request: muffin.Request) -> t.Optional[dict]:
        """Load a resource."""
        pk = request['path_params'].get(self.meta.name_id)
        if not pk:
            return None

        try:
            return await self.collection.find_one({self.meta.collection_id: bson.ObjectId(pk)})
        except bson.errors.InvalidId:
            raise APIError.NOT_FOUND()

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
        docs = resource if isinstance(resource, t.Sequence) else [resource]
        for doc in docs:
            if doc.get(self.meta.collection_id):
                await self.collection.replace_one(
                    {self.meta.collection_id: doc[self.meta.collection_id]}, doc)

            else:
                res = await self.meta.collection.insert_one(doc)
                doc[self.meta.collection_id] = res.inserted_id

        return resource

    async def remove(self, request: muffin.Request, *, resource: dict = None):
        """Remove the given resource(s)."""
        oids = [resource[self.meta.collection_id]] if resource else await request.data()
        if not oids:
            raise APIError.NOT_FOUND()

        if not isinstance(oids, list):
            raise APIError.BAD_REQUEST()

        oids = [bson.ObjectId(_id) for _id in oids]
        await self.meta.collection.delete_many({self.meta.collection_id: {'$in': oids}})

    delete = remove  # noqa
