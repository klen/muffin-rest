"""Base class for API Endpoints."""
from __future__ import annotations

import abc
import inspect
import json
import typing as t
from functools import partial

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
        name_id: str
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
        self.name_id = self.name_id or self.name

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
        name_id: str = ''  # Resource ID's name

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

    @classmethod
    def openapi(cls, route: Route, spec: APISpec) -> t.Dict:
        """Get openapi specs for the endpoint."""
        operations: t.Dict = {}
        summary, desc, schema = openapi.parse_docs(cls)
        if cls not in spec.tags:
            spec.tags[cls] = cls.meta.name
            spec.tag({'name': cls.meta.name, 'description': summary})
            spec.components.schema(cls.meta.Schema.__name__, schema=cls.meta.Schema)

        schema_ref = {'$ref': f"#/components/schemas/{ cls.meta.Schema.__name__ }"}
        for method in openapi.route_to_methods(route):
            operations[method] = {'tags': [spec.tags[cls]]}
            is_resource_route = isinstance(route, DynamicRoute) and \
                route.params.get(cls.meta.name_id)

            if method == 'get' and not is_resource_route:
                operations[method]['parameters'] = []
                if cls.meta.sorting:
                    sorting = list(cls.meta.sorting.keys())
                    operations[method]['parameters'].append({
                        'name': SORT_PARAM, 'in': 'query', 'style': 'form', 'explode': False,
                        'schema': {'type': 'array', 'items': {'type': 'string', 'enum': sorting}},
                        'description': ",".join(sorting),
                    })

                if cls.meta.filters.filters:
                    operations[method]['parameters'].append({
                        'name': FILTERS_PARAM, 'in': 'query', 'description': str(cls.meta.filters),
                        'content': {'application/json': {'schema': {'type': 'object'}}}
                    })

                if cls.meta.limit:
                    operations[method]['parameters'].append({
                        'name': LIMIT_PARAM, 'in': 'query',
                        'schema': {'type': 'integer', 'minimum': 1, 'maximum': cls.meta.limit},
                        'description': 'The number of items to return',
                    })
                    operations[method]['parameters'].append({
                        'name': OFFSET_PARAM, 'in': 'query',
                        'schema': {'type': 'integer', 'minimum': 0},
                        'description': 'The offset of items to return',
                    })

            # Update from the method
            meth = getattr(cls, method, None)
            if isinstance(route.target, partial) and '__meth__' in route.target.keywords:
                meth = getattr(cls, route.target.keywords['__meth__'], None)

            elif method in {'post', 'put'}:
                operations[method]['requestBody'] = {
                    'required': True, 'content': {'application/json': {'schema': schema_ref}}
                }

            if meth:
                operations[method]['summary'], operations[method]['description'], mschema = openapi.parse_docs(meth)  # noqa
                return_type = meth.__annotations__.get('return')
                if return_type == 'JSONType' or return_type == JSONType:
                    responses = {200: {'description': 'Request is successfull', 'content': {
                        'application/json': {'schema': schema_ref}
                    }}}
                else:
                    responses = openapi.return_type_to_response(meth)

                operations[method]['responses'] = responses
                operations[method] = openapi.merge_dicts(operations[method], mschema)

        return openapi.merge_dicts(operations, schema)
