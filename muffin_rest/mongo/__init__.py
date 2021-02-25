"""Mongo DB support."""

import typing as t

import bson
import marshmallow as ma
import muffin
from motor import motor_asyncio as motor

from ..endpoint import Endpoint, EndpointOpts
from ..errors import APIError
from ..filters import Filter, Filters
from .schema import MongoSchema
from .utils import MongoChain


class MongoFilter(Filter):
    """Custom filter for sqlalchemy."""

    operators = {
        '$eq': lambda n, v: ('$eq', v),
        '$ge': lambda n, v: ('$ge', v),
        '$gt': lambda n, v: ('$gt', v),
        '$in': lambda n, v: ('$in', v),
        '$le': lambda n, v: ('$le', v),
        '$lt': lambda n, v: ('$lt', v),
        '$ne': lambda n, v: ('$ne', v),
        '$nin': lambda n, v: ('$nin', v),
        '$starts': lambda n, v: ('$regex', f"^{ v }"),
        '$ends': lambda n, v: ('$regex', f"{ v }$"),
    }

    def apply(self, collection: MongoChain,
              ops: t.Tuple[t.Tuple[t.Callable, t.Any]], **kwargs) -> MongoChain:
        """Filter mongo."""
        return collection.find({self.attr: dict(op(self.name, v) for op, v in ops)})


class MongoFilters(Filters):
    """Bind MongoFilter class."""

    FILTER_CLASS = MongoFilter


class MongoEndpointOpts(EndpointOpts):
    """Support Mongo DB."""

    if t.TYPE_CHECKING:
        collection: motor.AsyncIOMotorCollection
        collection_id: str
        aggregate: t.Optional[t.List] = None  # Support aggregation. Set to pipeline.
        Schema: t.Type[MongoSchema]

    def __init__(self, cls):
        """Prepare meta options."""
        super().__init__(cls)

        if self.collection is None:
            return

        if self.Schema is MongoSchema:
            meta = type('Meta', (object,), self.schema_meta)
            self.Schema = type(self.name.title() + 'Schema', (MongoSchema,), dict(
                {'Meta': meta}, **(self.schema_fields or {})))


class MongoEndpoint(Endpoint):
    """Support Mongo DB."""

    meta: MongoEndpointOpts
    meta_class: t.Type[MongoEndpointOpts] = MongoEndpointOpts

    class Meta:
        """Tune mongo endpoints."""

        filters_cls = MongoFilters

        # Mongo options
        collection: t.Optional[motor.AsyncIOMotorCollection] = None
        collection_id = '_id'
        aggregate: t.Optional[t.List] = None  # Support aggregation. Set to pipeline.
        Schema = MongoSchema
        schema_fields = None

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

    async def sort(self, request: muffin.Request,
                   *sorting: t.Tuple[str, bool], **options) -> MongoChain:
        """Sort the current collection."""
        return self.collection.sort([(n, -1 if desc else 1) for n, desc in sorting])
