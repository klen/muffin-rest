"""Base class for API Endpoints."""
from __future__ import annotations

import abc
import inspect
import json
import typing as t

import marshmallow as ma
from asgi_tools.response import parse_response
from muffin import Request
from muffin._types import JSONType
from muffin.handler import Handler, HandlerMeta

from . import FILTERS_PARAM, LIMIT_PARAM, OFFSET_PARAM, SORT_PARAM, openapi
from .api import API
from .errors import APIError
from .filters import Filters, Filter


T = t.TypeVar('T')


class EndpointOpts:
    """Endpoints' options."""

    name: str = ''
    name_id: str = ''

    if t.TYPE_CHECKING:
        filters: Filters
        limit: int = 0
        sorting: t.Dict[str, bool] = {}
        Schema: t.Type[ma.Schema]

    def __init__(self, cls):
        """Inherit meta options."""
        for base in reversed(cls.mro()):
            if hasattr(base, "Meta"):
                for k, v in base.Meta.__dict__.items():
                    if not k.startswith('_'):
                        setattr(self, k, v)

        self.setup(cls)

    def setup(self, cls):
        """Setup the options."""
        # Setup names
        cls_name = cls.__name__
        self.name = self.name or cls_name.lower().split('endpoint', 1)[0] or cls_name.lower()
        self.name_id = self.name_id or self.name

        # Setup sorting
        if not isinstance(self.sorting, dict):
            self.sorting = dict(
                n if isinstance(n, (list, tuple)) else (n, bool(n)) for n in self.sorting)

        # Setup schema
        if not self.Schema:
            self.Schema = type(
                self.name.title() + 'Schema', (self.schema_base,),
                dict(self.schema_fields, Meta=self.setup_schema_meta(cls)))

    def setup_schema_meta(self, cls):
        """Generate meta for schemas."""
        return type('Meta', (object,), dict({'unknown': self.schema_unknown}, **self.schema_meta))

    def __repr__(self):
        """Represent self as a string."""
        return "<Options %s>" % self.name


class EndpointMeta(HandlerMeta):
    """Create class options."""

    def __new__(mcs, name, bases, params):
        """Prepare options for the endpoint."""
        cls = super().__new__(mcs, name, bases, params)
        if not getattr(cls.Meta, 'abc', False):
            cls.meta = cls.meta_class(cls)
            cls.meta.filters = cls.meta.filters_cls(*cls.meta.filters, endpoint=cls)
        return cls


class EndpointBase(Handler, metaclass=EndpointMeta):

    """Load/save resources."""

    if t.TYPE_CHECKING:
        collection: t.Any
        resource: t.Any
        meta: EndpointOpts

    meta_class: t.Type[EndpointOpts] = EndpointOpts
    _api: t.Optional[API] = None

    class Meta:
        """Tune the endpoint."""

        abc: bool = True                        # The class is abstract, meta wouldn't be generated

        name: str = ''                          # Resource's name
        name_id: str = ''                       # Resource ID's name

        # limit: Paginate results (set to None for disable pagination)
        limit: int = 0

        # Resource filters
        filters: t.Sequence[t.Union[str, t.Tuple[str, str], Filter]] = ()
        filters_cls: t.Type[Filters] = Filters

        # Define allowed resource sorting params
        sorting: t.Union[t.Dict[str, bool], t.Sequence[t.Union[str, t.Tuple[str, bool]]]] = {}

        # Auto generation for schemas
        schema_base: t.Type[ma.Schema] = ma.Schema
        schema_fields: t.Dict = {}
        schema_meta: t.Dict = {}
        schema_unknown: str = ma.EXCLUDE

        Schema: t.Optional[t.Type[ma.Schema]] = None

    @classmethod
    def __route__(cls, router, *paths, **params):
        """Bind the class to the given router."""
        methods = params.pop('methods') or cls.methods
        if paths:
            router.bind(cls, *paths, methods=methods, **params)

        else:
            router.bind(cls, f"/{ cls.meta.name }",
                        methods=methods & {'GET', 'POST', 'DELETE'}, **params)
            router.bind(cls, f"/{ cls.meta.name }/{{{ cls.meta.name_id }}}",
                        methods=methods & {'GET', 'PUT', 'DELETE'}, **params)

        for _, method in inspect.getmembers(cls, lambda m: hasattr(m, '__route__')):
            cpaths, cparams = method.__route__
            router.bind(cls, *cpaths, __meth__=method.__name__, **cparams)

        return cls

    async def __call__(self, request: Request, *args, __meth__: str = None, **options) -> t.Any:
        """Dispatch the given request by HTTP method."""
        method = getattr(self, __meth__ or request.method.lower())
        await self.authorize(request)
        self.collection = await self.prepare_collection(request)
        resource = await self.prepare_resource(request)
        if resource or request.method != 'GET':
            return await method(request, resource=resource)

        # Filter the collection
        filters = request.url.query.get(FILTERS_PARAM)
        if filters:
            try:
                data = json.loads(filters)
                _, self.collection = self.meta.filters.filter(data, self.collection, endpoint=self)

            except (ValueError, TypeError):
                self.api.logger.warning('Invalid filters data: request.url')

        # Sort resources
        if SORT_PARAM in request.url.query:
            sorting = [
                (name.strip('-'), name.startswith('-'))
                for name in request.url.query[SORT_PARAM].split(',')
                if name.strip('-') in self.meta.sorting]

            self.collection = await self.sort(request, *sorting, **options)

        # Paginate the collection
        headers = {}
        limit = request.url.query.get(LIMIT_PARAM) or self.meta.limit
        if self.meta.limit and limit:
            try:
                limit = min(abs(int(limit)), self.meta.limit)
                offset = int(request.url.query.get(OFFSET_PARAM, 0))
                if limit and offset >= 0:
                    self.collection, total = await self.paginate(
                        request, limit=limit, offset=offset)
                    headers = self.paginate_prepare_headers(limit, offset, total)

            except ValueError:
                raise APIError.BAD_REQUEST('Pagination params are invalid')

        response = await method(request, resource=resource)
        if headers:
            response = parse_response(response)
            response.headers.update(headers)

        return response

    @abc.abstractmethod
    async def prepare_collection(self, request: Request) -> t.Any:
        """Prepare a collection of resources. Create queryset, db cursor and etc."""
        raise NotImplementedError

    @abc.abstractmethod
    async def paginate(self, request: Request, *, limit: int = 0,
                       offset: int = 0) -> t.Tuple[t.Any, int]:
        """Paginate the results."""
        raise NotImplementedError

    def paginate_prepare_headers(self, limit, offset, total):
        """Prepare pagination headers."""
        return {'x-total': total, 'x-limit': limit, 'x-offset': offset}

    @abc.abstractmethod
    async def save(self, request: Request, *, resource: T = None) -> T:
        """Save the given resource."""
        raise NotImplementedError

    @abc.abstractmethod
    async def remove(self, request: Request, *, resource: t.Any = None):
        """Remove the given resource."""
        raise NotImplementedError

    @abc.abstractmethod
    async def sort(self, request: Request, *sorting: t.Tuple[str, bool], **options) -> t.Any:
        """Remove the given resource."""
        raise NotImplementedError

    @property
    def api(self) -> API:
        """Check if the endpoint bind to an API."""
        if self._api is None:
            raise Exception('The endpoint is not routed by any API')  # TODO
        return self._api

    async def authorize(self, request: Request):
        """Default authorization method. Proxy auth to self.api."""
        auth = await self.api.authorize(request)
        if not auth:
            raise APIError.UNAUTHORIZED()

    async def get_schema(self, request: Request, resource=None) -> ma.Schema:
        """Initialize marshmallow schema for serialization/deserialization."""
        assert self.meta.Schema, 'Endpoint.meta.Schema is required.'
        return self.meta.Schema(
            only=request.url.query.get('schema_only'),
            exclude=request.url.query.get('schema_exclude', ()),
        )

    async def dump(self, request: Request, response: t.Any, *, many=...) -> JSONType:
        """Serialize the given response."""
        schema = await self.get_schema(request)
        if many is ...:
            many = isinstance(response, t.Sequence)

        return schema.dump(response, many=many) if schema else response

    async def get(self, request, *, resource=None) -> JSONType:
        """Get a resource or a collection of resources.

        Specify a path param to load a resource.
        """
        if resource is not None and resource != '':
            return await self.dump(request, resource)

        return await self.dump(request, self.collection, many=True)

    async def post(self, request, *, resource=None) -> JSONType:
        """Create a resource.

        The method accepts a single resource's data or a list of resources to create.
        """
        resource = await self.load(request, resource=resource)
        resource = await self.save(request, resource=resource)
        return await self.dump(request, resource, many=isinstance(resource, list))

    async def put(self, request, *, resource=None) -> JSONType:
        """Update a resource."""
        if resource is None:
            raise APIError.NOT_FOUND()

        return await self.post(request, resource=resource)

    async def delete(self, request, *, resource=None):
        """Delete a resource."""
        if resource is None:
            raise APIError.NOT_FOUND()

        return await self.remove(request, resource=resource)

    async def prepare_resource(self, request: Request) -> t.Any:
        """Load a resource."""
        return request['path_params'].get(self.meta.name_id)

    async def load(self, request: Request, *, resource: t.Any = None) -> t.Any:
        """Load data from request and create/update a resource."""
        try:
            data = await request.data()
        except (ValueError, TypeError) as exc:
            raise APIError.BAD_REQUEST(str(exc))

        schema = await self.get_schema(request, resource=resource)
        if not schema:
            return data

        try:
            resource = schema.load(data, partial=resource is not None, many=isinstance(data, list))  # type: ignore # noqa
        except ma.ValidationError as exc:
            raise APIError.BAD_REQUEST('Invalid data', errors=exc.messages)

        return resource


class Endpoint(EndpointBase, openapi.OpenAPIMixin):
    """Basic endpoint class."""

    class Meta:
        """Tune the endpoint."""

        abc: bool = True                        # The class is abstract, meta wouldn't be generated
