"""Base class for API REST Handlers."""

import abc
import inspect
from typing import (
    Any,
    Generator,
    Generic,
    Iterable,
    Literal,
    Mapping,
    Sequence,
    cast,
    overload,
)

import marshmallow as ma
from asgi_tools.response import ResponseJSON, parse_response
from muffin import Request
from muffin.handler import Handler, HandlerMeta

from muffin_rest import LIMIT_PARAM, OFFSET_PARAM, openapi
from muffin_rest.api import API
from muffin_rest.errors import APIError
from muffin_rest.filters import Filter
from muffin_rest.marshmallow import load_data
from muffin_rest.sorting import Sort
from muffin_rest.types import TSchemaRes

from .errors import HandlerNotBindedError
from .options import RESTOptions
from .types import TVCollection, TVResource


class RESTHandlerMeta(HandlerMeta):
    """Create class options."""

    def __new__(mcs, name, bases, params):
        """Prepare options for the handler."""
        kls = cast("type[RESTBase]", super().__new__(mcs, name, bases, params))
        kls.meta = kls.meta_class(kls)

        if getattr(kls.meta, kls.meta_class.base_property, None) is not None:
            kls.meta.filters = kls.meta.filters_cls(kls, kls.meta.filters)
            kls.meta.sorting = kls.meta.sorting_cls(kls, kls.meta.sorting)

        return kls


class RESTBase(Generic[TVResource], Handler, metaclass=RESTHandlerMeta):
    """Load/save resources."""

    auth: Any
    collection: Any
    resource: Any

    meta: RESTOptions
    meta_class: type[RESTOptions] = RESTOptions
    _api: API | None = None

    filters: dict[str, Any] | None = None
    sorting: dict[str, Any] | None = None

    class Meta:
        """Tune the handler."""

        # Resource filters
        filters: Sequence[str | tuple[str, str] | Filter] = ()

        # Define allowed resource sorting params
        sorting: Sequence[str | tuple[str, dict] | Sort] = ()

        # Serialize/Deserialize Schema class
        Schema: type[ma.Schema] | None = None

    @classmethod
    def __route__(cls, router, *paths, **params):
        """Bind the class to the given router."""
        methods = params.pop("methods") or cls.methods
        if paths:
            router.bind(cls, *paths, methods=methods, **params)

        else:
            router.bind(cls, f"/{ cls.meta.name }", methods=methods, **params)
            router.bind(cls, f"/{ cls.meta.name }/{{pk}}", methods=methods, **params)

        for _, method in inspect.getmembers(cls, lambda m: hasattr(m, "__route__")):
            paths, methods = method.__route__
            router.bind(cls, *paths, methods=methods, method_name=method.__name__)

        return cls

    async def __call__(self, request: Request, *, method_name: str | None = None, **_) -> Any:
        """Dispatch the given request by HTTP method."""
        self.auth = await self.authorize(request)

        meta = self.meta

        self.collection = await self.prepare_collection(request)
        resource = await self.prepare_resource(request)
        method = getattr(self, method_name or request.method.lower())
        if not (request.method == "GET" and resource is None and not method_name):
            return await method(request, resource=resource)

        # Filter collection
        self.collection, self.filters = await self.filter(request, self.collection)

        # Sort collection
        self.collection, self.sorting = await self.sort(request, self.collection)

        # Paginate the collection
        headers = None
        if meta.limit:
            limit, offset = self.paginate_prepare_params(request)
            if limit and offset >= 0:
                self.collection, total = await self.paginate(request, limit=limit, offset=offset)
                headers = self.paginate_prepare_headers(limit, offset, total)

        response = await method(request)

        if headers:
            response = parse_response(response)
            response.headers.update(headers)

        return response

    @property
    def api(self) -> API:
        """Check if the handler is binded to an API."""
        if self._api is None:
            raise HandlerNotBindedError
        return self._api

    async def authorize(self, request: Request) -> Any:
        """Default authorization method. Proxy auth to self.api."""
        auth = await self.api.authorize(request)
        if not auth:
            raise APIError.UNAUTHORIZED()
        return auth

    # Prepare data
    # ------------
    @abc.abstractmethod
    async def prepare_collection(self, request: Request) -> Any:
        """Prepare a collection of resources. Create queryset, db cursor and etc."""
        raise NotImplementedError

    async def prepare_resource(self, request: Request) -> Any:
        """Load a resource."""
        return request["path_params"].get("pk")

    async def filter(self, request: Request, collection: TVCollection) -> tuple[TVCollection, Any]:
        """Filter the collection."""
        filters = self.meta.filters
        if filters:
            return await filters.apply(request, collection)

        return collection, None

    async def sort(self, request: Request, collection: TVCollection) -> tuple[TVCollection, Any]:
        sorting = self.meta.sorting
        if sorting:
            return await sorting.apply(request, collection)

        return collection, None

    # Paginate
    # --------
    def paginate_prepare_headers(self, limit, offset, total=None):
        """Prepare pagination headers."""
        headers = {"x-limit": limit, "x-offset": offset}
        if total is not None:
            headers["x-total"] = total
        return headers

    def paginate_prepare_params(self, request: Request) -> tuple[int, int]:
        """Prepare pagination params."""
        meta = self.meta
        query = request.url.query
        limit = query.get(LIMIT_PARAM) or meta.limit
        try:
            return min(abs(int(limit)), meta.limit_max), int(query.get(OFFSET_PARAM, 0))
        except ValueError as exc:
            raise APIError.BAD_REQUEST("Pagination params are invalid") from exc

    @abc.abstractmethod
    async def paginate(
        self, request: Request, *, limit: int = 0, offset: int = 0
    ) -> tuple[Any, int | None]:
        """Paginate the results."""
        raise NotImplementedError

    # Manage data
    # -----------
    @abc.abstractmethod
    async def save(self, request: Request, resource: TVResource, *, update=False) -> TVResource:
        """Save the given resource."""
        return resource

    async def save_many(
        self, request: Request, data: list[TVResource], *, update=False
    ) -> list[TVResource]:
        """Save many resources."""
        return [await self.save(request, item, update=update) for item in data]

    @abc.abstractmethod
    async def remove(self, request: Request, resource):
        """Remove the given resource."""
        raise NotImplementedError

    # Parse data
    # -----------
    def get_schema(
        self, request: Request, *, resource: TVResource | None = None, **schema_options
    ) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        query = request.url.query
        schema_options.setdefault("only", query.get("schema_only"))
        schema_options.setdefault("exclude", query.get("schema_exclude", ()))
        return self.meta.Schema(**schema_options)

    async def load_data(self, request: Request):
        """Load data from request and create/update a resource."""
        try:
            data = await request.data(raise_errors=True)
        except (ValueError, TypeError) as err:
            raise APIError.BAD_REQUEST(str(err)) from err

        return data

    async def load(self, request: Request, resource: TVResource | None = None, **schema_options):
        """Load data from request and create/update a resource."""
        schema = self.get_schema(request, resource=resource, **schema_options)
        data = cast("Mapping | list", await self.load_data(request))
        return cast(
            "TVResource | list[TVResource]",
            await load_data(data, schema, partial=resource is not None),
        )

    @overload
    async def dump(  # type: ignore[misc]
        self, request, data: TVResource | Iterable[TVResource], *, many: Literal[True]
    ) -> list[TSchemaRes]: ...

    @overload
    async def dump(
        self, request, data: TVResource | Iterable[TVResource], *, many: bool = False
    ) -> TSchemaRes: ...

    async def dump(
        self,
        request: Request,
        data: TVResource | Iterable[TVResource],
        *,
        many: bool = False,
    ) -> TSchemaRes | list[TSchemaRes]:
        """Serialize the given response."""
        schema = self.get_schema(request)
        return schema.dump(data, many=many)

    async def get(self, request: Request, *, resource: TVResource | None = None) -> ResponseJSON:
        """Get a resource or a collection of resources.

        Specify a path param to load a resource.
        """
        res = await (
            self.dump(request, resource)
            if resource
            else self.dump(request, data=self.collection, many=True)
        )
        return ResponseJSON(res)  # type: ignore[type-var]

    async def post(self, request: Request, *, resource: TVResource | None = None) -> ResponseJSON:
        """Create a resource.

        The method accepts a single resource's data or a list of resources to create.
        """
        data = await self.load(request, resource)
        many = isinstance(data, list)
        if many:
            data = await self.save_many(request, data, update=resource is not None)
        else:
            data = await self.save(request, cast("TVResource", data), update=resource is not None)

        res = await self.dump(request, data, many=many)
        return ResponseJSON(res)

    async def put(self, request: Request, *, resource: TVResource | None = None) -> ResponseJSON:
        """Update a resource."""
        if resource is None:
            raise APIError.NOT_FOUND()

        return await self.post(request, resource=resource)

    async def delete(self, request: Request, resource: TVResource | None = None):
        """Delete a resource."""
        if resource is None:
            raise APIError.NOT_FOUND()

        res = await self.remove(request, resource)
        return ResponseJSON(res)


class RESTHandler(RESTBase[TVResource], openapi.OpenAPIMixin):
    """Basic Handler Class."""


def to_sort(sort_params: Sequence[str]) -> Generator[tuple[str, bool], None, None]:
    """Generate sort params."""
    for name in sort_params:
        n, desc = name.strip("-"), name.startswith("-")
        if n:
            yield n, desc
