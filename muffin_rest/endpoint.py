"""Base class for API Endpoints."""
import abc
import json
import typing as t

import marshmallow as ma
from asgi_tools.response import parse_response
from muffin import Request
from muffin._types import JSONType
from muffin.handler import Handler, HandlerMeta

from .api import API
from .errors import APIError
from .filters import Filters, Filter


T = t.TypeVar('T')

FILTERS_PARAM = 'where'
LIMIT_PARAM = 'limit'
SORT_PARAM = 'sort'
OFFSET_PARAM = 'offset'


class EndpointOpts:
    """Endpoints' options."""

    name: str

    filters: Filters

    limit: int = 0

    sorting: t.Dict[str, bool] = {}

    Schema: t.Optional[t.Type[ma.Schema]] = None

    def __init__(self, cls):
        """Prepare meta options."""
        for base in reversed(cls.mro()):
            if not hasattr(base, "Meta"):
                continue

            for k, v in base.Meta.__dict__.items():
                if k.startswith('__'):
                    continue
                setattr(self, k, v)

        # Generate name
        self.name = self.name or cls.__name__.lower().split('endpoint', 1)[0] or\
            cls.__name__.lower()

        # Setup filters
        self.filters = self.filters_converter(*self.filters, endpoint=cls)

        # Setup sorting
        if not isinstance(self.sorting, dict):
            self.sorting = dict(
                n if isinstance(n, (list, tuple)) else (n, bool(n)) for n in self.sorting)

    def __repr__(self):
        """Represent self as a string."""
        return "<Options %s>" % self.name


class EndpointMeta(HandlerMeta):
    """Create class options."""

    def __new__(mcs, name, bases, params):
        """Prepare options for the endpoint."""
        cls = super().__new__(mcs, name, bases, params)
        cls.meta = cls.meta_class(cls)
        return cls


class Endpoint(Handler, metaclass=EndpointMeta):

    """Load/save resources."""

    collection: t.Any
    resource: t.Any
    filters: t.Dict
    meta: EndpointOpts
    meta_class: t.Type[EndpointOpts] = EndpointOpts

    class Meta:
        """Tune the endpoint."""

        name: str = ''  # Resource's name

        # Tune Schema
        Schema: t.Optional[t.Type[ma.Schema]] = None
        schema_meta: t.Dict = {}

        # limit: Paginate results (set to None for disable pagination)
        limit: int = 0

        # Resource filters
        filters: t.Sequence[t.Union[str, Filter]] = ()

        # Filters converter class
        filters_converter: t.Type[Filters] = Filters

        # Define allowed resource sorting params
        sorting: t.Union[t.Dict[str, bool], t.Sequence[t.Union[str, t.Tuple[str, bool]]]] = {}

    _api: t.Optional[API] = None

    async def __call__(self, request: Request, *args, **options) -> t.Any:
        """Dispatch the given request by HTTP method."""
        method = getattr(self, options.get('__meth__') or request.method.lower())
        await self.authorize(request)
        self.collection = await self.prepare_collection(request)
        if request.method == 'POST':
            return await self.post(request, **options)

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
                limit = int(limit)
                offset = int(request.url.query.get(OFFSET_PARAM, 0))
                if limit and offset >= 0:
                    self.collection, total = await self.paginate(
                        request, limit=limit, offset=offset)
                    headers = {'x-total': total, 'x-limit': limit, 'x-offset': offset}

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

    @abc.abstractmethod
    async def save(self, request: Request, *, resource: T = None) -> T:
        """Save the given resource."""
        raise NotImplementedError

    @abc.abstractmethod
    async def remove(self, request: Request, *, resource: t.Any = None):
        """Remove the given resource."""
        raise NotImplementedError

    @abc.abstractmethod
    async def sort(self, request: Request, *sorting: t.Tuple[str, bool], **options):
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

    async def get(self, request, *, resource=None):
        """Get resource or collection of resources."""
        if resource is not None and resource != '':
            return await self.dump(request, resource)

        return await self.dump(request, self.collection, many=True)

    async def post(self, request, *, resource=None):
        """Create a resource."""
        resource = await self.load(request, resource=resource)
        resource = await self.save(request, resource=resource)
        return await self.dump(request, resource, many=isinstance(resource, list))

    async def put(self, request, *, resource=None):
        """Update a resource."""
        if resource is None:
            raise APIError.NOT_FOUND()

        return await self.post(request, resource=resource)

    patch = put

    async def delete(self, request, *, resource=None):
        """Delete a resource."""
        if resource is None:
            raise APIError.NOT_FOUND()

        return await self.remove(request, resource=resource)

    async def prepare_resource(self, request: Request) -> t.Any:
        """Load a resource."""
        return request['path_params'].get(self.meta.name)

    async def get_schema(self, request: Request, resource=None) -> t.Optional[ma.Schema]:
        """Initialize marshmallow schema for serialization/deserialization."""
        return self.meta.Schema(
            only=request.url.query.get('schema_only'),
            exclude=request.url.query.get('schema_exclude', ()),
        ) if self.meta.Schema else None

    async def dump(
            self, request: Request, response: T, *,
            many: bool = ...) -> t.Union[T, JSONType]:  # type: ignore
        """Serialize the given response."""
        schema = await self.get_schema(request)
        if many is ...:
            many = isinstance(response, t.Sequence)

        return schema.dump(response, many=many) if schema else response

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
