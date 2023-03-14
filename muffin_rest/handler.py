"""Base class for API REST Handlers."""

from __future__ import annotations

import abc
import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generator,
    Generic,
    Iterable,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

from asgi_tools.response import parse_response
from asgi_tools.types import TJSON
from marshmallow import ValidationError
from muffin.handler import Handler, HandlerMeta

from muffin_rest import LIMIT_PARAM, OFFSET_PARAM, openapi
from muffin_rest.errors import APIError

from .errors import HandlerNotBindedError
from .options import RESTOptions
from .types import TVResource

if TYPE_CHECKING:
    import marshmallow as ma
    from muffin import Request

    from muffin_rest.api import API
    from muffin_rest.filters import Filter
    from muffin_rest.sorting import Sort


class RESTHandlerMeta(HandlerMeta):
    """Create class options."""

    def __new__(mcs, name, bases, params):
        """Prepare options for the handler."""
        kls = super().__new__(mcs, name, bases, params)
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
    meta_class: Type[RESTOptions] = RESTOptions
    _api: Optional[API] = None

    class Meta:
        """Tune the handler."""

        # Resource filters
        filters: Sequence[Union[str, Tuple[str, str], Filter]] = ()

        # Define allowed resource sorting params
        sorting: Sequence[Union[str, Tuple[str, Dict], Sort]] = ()

        # Serialize/Deserialize Schema class
        Schema: Optional[Type[ma.Schema]] = None

    @classmethod
    def __route__(cls, router, *paths, **params):
        """Bind the class to the given router."""
        methods = params.pop("methods") or cls.methods
        if paths:
            router.bind(cls, *paths, methods=methods, **params)

        else:
            router.bind(cls, f"/{ cls.meta.name }", methods=methods, **params)
            router.bind(
                cls,
                f"/{ cls.meta.name }/{{{ cls.meta.name_id }}}",
                methods=methods,
                **params,
            )

        for _, method in inspect.getmembers(cls, lambda m: hasattr(m, "__route__")):
            cpaths, cparams = method.__route__
            router.bind(cls, *cpaths, __meth__=method.__name__, **cparams)

        return cls

    async def __call__(
        self,
        request: Request,
        *,
        __meth__: Optional[str] = None,
        **options,
    ) -> Any:
        """Dispatch the given request by HTTP method."""
        method = getattr(self, __meth__ or request.method.lower())
        self.auth = await self.authorize(request)
        self.collection = await self.prepare_collection(request)
        resource = await self.prepare_resource(request)
        if resource or request.method != "GET":
            try:
                return await method(request, resource=resource)
            except ValidationError as exc:
                raise APIError.BAD_REQUEST("Invalid data", errors=exc.messages) from exc

        meta = self.meta

        # Filter collection
        if meta.filters:
            self.collection = await meta.filters.apply(
                request,
                self.collection,
                **options,
            )

        # Sort collection
        if meta.sorting:
            self.collection = await meta.sorting.apply(
                request,
                self.collection,
                **options,
            )

        # Paginate the collection
        headers = {}
        if meta.limit:
            limit, offset = self.paginate_prepare_params(request)
            if limit and offset >= 0:
                self.collection, total = await self.paginate(
                    request,
                    limit=limit,
                    offset=offset,
                )
                headers = self.paginate_prepare_headers(limit, offset, total)

        response = await method(request, resource=resource)

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
        return request["path_params"].get(self.meta.name_id)

    # Paginate
    # --------
    def paginate_prepare_headers(self, limit, offset, total):
        """Prepare pagination headers."""
        return {"x-total": total, "x-limit": limit, "x-offset": offset}

    def paginate_prepare_params(self, request: Request) -> Tuple[int, int]:
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
        self,
        request: Request,
        *,
        limit: int = 0,
        offset: int = 0,
    ) -> Tuple[Any, int]:
        """Paginate the results."""
        raise NotImplementedError

    # Manage data
    # -----------
    @abc.abstractmethod
    async def save(self, request: Request, resource: TVResource) -> TVResource:
        """Save the given resource."""
        return resource

    @abc.abstractmethod
    async def remove(self, request: Request, resource):
        """Remove the given resource."""
        raise NotImplementedError

    # Parse data
    # -----------
    async def get_schema(self, request: Request, **_) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        assert self.meta.Schema, "RESTHandler.meta.Schema is required."
        query = request.url.query
        return self.meta.Schema(
            only=query.get("schema_only"),
            exclude=query.get("schema_exclude", ()),
        )

    async def parse(self, request: Request):
        """Parse data from the given request."""
        try:
            return await request.data(raise_errors=True)
        except (ValueError, TypeError) as exc:
            raise APIError.BAD_REQUEST(str(exc)) from exc

    async def load(
        self,
        request: Request,
        resource: Optional[TVResource] = None,
    ) -> Any:
        """Load data from request and create/update a resource."""
        data = await self.parse(request)
        schema = await self.get_schema(request, resource=resource)
        if not schema:
            return data

        return schema.load(
            data,
            partial=resource is not None,
            many=isinstance(data, list),
        )

    async def dump(
        self,
        request: Request,
        data: Optional[Iterable] = None,
        resource: Optional[TVResource] = None,
        **dump_schema_opts,
    ) -> TJSON:
        """Serialize the given response."""
        schema = await self.get_schema(request, resource=resource)
        if schema:
            return schema.dump(
                resource if resource is not None else data,
                **dump_schema_opts,
            )

        return cast(TJSON, data)

    async def get(self, request: Request, *, resource: Optional[TVResource] = None):
        """Get a resource or a collection of resources.

        Specify a path param to load a resource.
        """
        if resource:
            return await self.dump(request, resource=resource)

        return await self.dump(request, data=self.collection, many=True)

    async def post(self, request: Request, *, resource: Optional[TVResource] = None):
        """Create a resource.

        The method accepts a single resource's data or a list of resources to create.
        """
        data = await self.load(request, resource)
        if isinstance(data, list):
            return await self.dump(
                request,
                data=[await self.save(request, res) for res in data],
                many=True,
            )

        res = await self.save(request, data)
        return await self.dump(request, resource=res)

    async def put(self, request: Request, *, resource: Optional[TVResource] = None):
        """Update a resource."""
        if resource is None:
            raise APIError.NOT_FOUND()

        return await self.post(request, resource=resource)

    async def delete(self, request: Request, resource: TVResource | None = None):
        """Delete a resource."""
        if resource is None:
            raise APIError.NOT_FOUND()

        return await self.remove(request, resource)


class RESTHandler(RESTBase, openapi.OpenAPIMixin):
    """Basic Handler Class."""


def to_sort(
    sort_params: Sequence[str],
) -> Generator[Tuple[str, bool], None, None]:
    """Generate sort params."""
    for name in sort_params:
        n, desc = name.strip("-"), name.startswith("-")
        if n:
            yield n, desc
