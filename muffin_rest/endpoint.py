"""Base class for API Endpoints."""
from __future__ import annotations

import abc
import json
import typing as t

import marshmallow as ma
from apispec import APISpec
from asgi_tools.response import parse_response
from http_router.routes import Route, DynamicRoute
from muffin import Request
from muffin._types import JSONType
from muffin.handler import Handler, HandlerMeta

from . import openapi
from .api import API
from .errors import APIError
from .filters import Filters, Filter


T = t.TypeVar('T')

FILTERS_PARAM = 'where'
LIMIT_PARAM = 'limit'
OFFSET_PARAM = 'offset'
SORT_PARAM = 'sort'


class EndpointOpts:
    """Endpoints' options."""

    if t.TYPE_CHECKING:
        name: str
        filters: Filters
        Schema: t.Type[ma.Schema]
        limit: int = 0
        sorting: t.Dict[str, bool] = {}

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
        cls.meta.filters = cls.meta.filters_cls(*cls.meta.filters, endpoint=cls)
        return cls


class Endpoint(Handler, metaclass=EndpointMeta):

    """Load/save resources."""

    if t.TYPE_CHECKING:
        collection: t.Any
        resource: t.Any
        meta: EndpointOpts

    meta_class: t.Type[EndpointOpts] = EndpointOpts
    _api: t.Optional[API] = None

    class Meta:
        """Tune the endpoint."""

        name: str = ''  # Resource's name

        # Tune Schema
        Schema: t.Optional[t.Type[ma.Schema]] = None
        schema_meta: t.Dict = {}

        # limit: Paginate results (set to None for disable pagination)
        limit: int = 0

        # Resource filters
        filters: t.Sequence[t.Union[str, t.Tuple[str, str], Filter]] = ()
        filters_cls: t.Type[Filters] = Filters

        # Define allowed resource sorting params
        sorting: t.Union[t.Dict[str, bool], t.Sequence[t.Union[str, t.Tuple[str, bool]]]] = {}

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
        return request['path_params'].get(self.meta.name)

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

    @classmethod
    def openapi(cls, route: Route, spec: APISpec) -> t.Dict:
        """Prepare the endpoint for openapi specs."""
        operations: t.Dict = {}
        schema_ref = None
        summary, desc, schema = openapi.parse_docs(cls)
        if cls not in spec.tags:
            spec.tags[cls] = cls.meta.name
            spec.tag({'name': cls.meta.name, 'description': summary})
            spec.components.schema(cls.meta.Schema.__name__, schema=cls.meta.Schema)

        schema_ref = {'$ref': f"#/components/schemas/{ cls.meta.Schema.__name__ }"}

        for method in openapi.route_to_methods(route):
            if not isinstance(route, DynamicRoute):
                if method in {'put', 'patch', 'delete'}:
                    continue
            elif route.params.get(cls.meta.name) and method == 'post':
                continue

            operations[method] = {}
            if method in {'post', 'put'}:
                operations[method]['requestBody'] = {
                    'required': True,
                    'content': {
                        'application/json': {'schema': schema_ref}
                    }
                }

            meth = getattr(cls, method, None)
            if meth is None:
                continue

            operations[method]['summary'], operations[method]['description'], _ = openapi.parse_docs(meth)  # noqa
            operations[method]['tags'] = [spec.tags[cls]]
            return_type = meth.__annotations__.get('return')
            if return_type == 'JSONType':
                responses = {200: {'description': 'Request is successfull', 'content': {
                    'application/json': {'schema': schema_ref}
                }}}
            else:
                responses = openapi.return_type_to_response(meth)

            operations[method]['responses'] = responses

        operations = openapi.merge_dicts(operations, schema)

        return operations
