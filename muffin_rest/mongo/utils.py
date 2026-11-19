"""Mongo Utils."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable

if TYPE_CHECKING:
    from motor import motor_asyncio as motor


class MongoChain:
    """Support query chains.

    Only for `find` and `find_one` methods.
    ::
        collection = MongoChain(mongo_collection)
        collection = collection.find({'field': 'value').find('field2': 'value')
        result = collection.find_one({'field3': 'value')
        results = collection.skip(10).limit(10)
    """

    CURSOR_METHODS = (
        "where",
        "sort",
        "skip",
        "rewind",
        "retrieved",
        "remove_option",
        "next",
        "min",
        "max_time_ms",
        "max_scan",
        "max_await_time_ms",
        "max",
        "limit",
        "hint",
        "explain",
        "distinct",
        "cursor_id",
        "count",
        "comment",
        "collection",
        "close",
        "clone",
        "batch_size",
        "alive",
        "address",
        "add_option",
        "__getitem__",
    )

    def __init__(self, collection: motor.AsyncIOMotorCollection) -> None:
        """Initialize the resource."""
        self.collection = collection
        self.query: list = []
        self.projection = None
        self.sorting: list[tuple[str, int]] = []

    def find(
        self,
        query: list | dict | None = None,
        projection: dict | None = None,
    ) -> MongoChain:
        """Store filters in self."""
        self.query = self.__update__(query)
        self.projection = projection
        return self

    def find_one(
        self,
        query: list | dict | None = None,
        projection: dict | None = None,
    ) -> Awaitable:
        """Apply filters and return cursor."""
        query = self.__update__(query)
        query = (query and {"$and": query}) or {}
        return self.collection.find_one(query, projection=projection)

    def count(self) -> Awaitable[int]:
        """Count documents."""
        query = (self.query and {"$and": self.query}) or {}
        return self.collection.count_documents(query)  # type: ignore[]

    def aggregate(self, pipeline: list, **kwargs: Any) -> Any:
        """Aggregate collection."""
        if self.query:
            for params in pipeline:
                if "$match" in params:
                    query = self.__update__(params["$match"])
                    params["$match"] = {"$and": query}
                    break
            else:
                pipeline.insert(0, {"$match": {"$and": self.query}})

        if self.sorting:
            pipeline = [p for p in pipeline if "$sort" not in p]
            pipeline.append({"$sort": dict(self.sorting)})

        return self.collection.aggregate(pipeline, **kwargs)

    def sort(self, key: str | list, direction: int = 1) -> MongoChain:
        """Save ordering properties."""
        if isinstance(key, str):
            self.sorting.append((key, direction))

        else:
            self.sorting = key

        return self

    def __repr__(self) -> str:
        """String representation."""
        return "<MongoChain (%s) %r>" % (self.collection.name, self.query)

    def __update__(self, query: Any) -> list:
        """Update stored query."""
        if query:
            self.query.append(query)

        return self.query

    def _cursor(self) -> Any:
        """Build a motor cursor from the stored query and sorting."""
        query = (self.query and {"$and": self.query}) or {}
        cursor = self.collection.find(query, self.projection)
        if self.sorting:
            cursor = cursor.sort(self.sorting)
        return cursor

    def __iter__(self) -> Any:
        """Iterate by self collection."""
        return self._cursor()

    async def to_list(self, length: int | None = None) -> list:
        """Fetch documents as a list."""
        return await self._cursor().to_list(length)

    def __getattr__(self, name: str) -> Any:
        """Proxy any attributes except find to self.collection."""
        if name in self.CURSOR_METHODS:
            return getattr(self._cursor(), name)
        return getattr(self.collection, name)
