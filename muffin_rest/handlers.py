"""REST Handler."""
import math
from asyncio import iscoroutine
from urllib.parse import urlencode

from aiohttp.web import StreamResponse, Response
from muffin.handler import Handler
from ujson import dumps, loads # noqa

from .filters import Filters
from .exceptions import RESTNotFound, RESTBadRequest


VAR_PAGE = 'page'
VAR_PER_PAGE = 'per_page'
VAR_SORT = 'sort'
VAR_WHERE = 'where'


class RESTOptions(object):

    """Prepare resource options."""

    def __init__(self, cls, **params):
        """Process meta options."""
        # Store link to self.meta
        self.meta = getattr(cls, "Meta", None)

        self.cls = cls

        # Inherit meta from parents
        for base in reversed(cls.mro()):
            if not hasattr(base, "Meta"):
                continue

            for k, v in base.Meta.__dict__.items():
                if k.startswith('__'):
                    continue
                setattr(self, k, v)

        # Generate name
        cls.name = getattr(cls, 'name', None) or cls.__name__.lower().split('resource', 1)[0]

        self.per_page = int(self.per_page or 0)

        # Setup schema_meta
        self.schema_meta = self.schema_meta or {
            k[7:]: self.__dict__[k] for k in self.__dict__
            if k.startswith('schema_') and not k == 'schema_meta'
        }

        # Setup filters
        self.filters = self.filters_converter(*self.filters, handler=cls)

    def __repr__(self):
        """String representation."""
        return "<Options %s>" % self.cls


class RESTHandlerMeta(type(Handler)):

    """Create options class."""

    def __new__(mcs, name, bases, params):
        """Initialize options class."""
        params_ = dict(params)
        cls = super(RESTHandlerMeta, mcs).__new__(mcs, name, bases, params)
        cls.meta = cls.OPTIONS_CLASS(cls, **params_)
        return cls


class RESTHandler(Handler, metaclass=RESTHandlerMeta):

    """Implement a common handler for REST operations."""

    OPTIONS_CLASS = RESTOptions

    Schema = None

    class Meta:

        """Default options."""

        # per_page: Paginate results (set to None for disable pagination)
        per_page = None
        page_links = False

        # Resource filters
        filters = ()

        # Filters converter class
        filters_converter = Filters

        # Redefine Schema.Meta completely
        schema_meta = None

    def __init__(self, *args, **kwargs):
        """Init the resource state."""
        super(RESTHandler, self).__init__(*args, **kwargs)
        self.filters = self.auth = self.collection = None

    @classmethod
    def bind(cls, app, *paths, methods=None, name=None, **kwargs):
        """Bind to the application.

        Generate URL, name if it's not provided.
        """
        paths = paths or ['/%s(/{%s})?/?' % (cls.name, cls.name)]
        name = name or "api.%s" % cls.name
        return super(RESTHandler, cls).bind(app, *paths, methods=methods, name=name, **kwargs)

    async def dispatch(self, request, view=None, **kwargs):
        """Process request."""
        # Authorization endpoint
        self.auth = await self.authorize(request, **kwargs)  # noqa

        # Load collection
        self.collection = await self.get_many(request, **kwargs)

        if request.method == 'POST' and view is None:
            return await super(RESTHandler, self).dispatch(request, **kwargs)

        # Load resource
        resource = await self.get_one(request, **kwargs)

        headers = {}

        if request.method == 'GET' and resource is None:

            # Filter resources
            if VAR_WHERE in request.query:
                self.collection = await self.filter(request, **kwargs)

            # Sort resources
            if VAR_SORT in request.query:
                sorting = [(name.strip('-'), name.startswith('-'))
                           for name in request.query[VAR_SORT].split(',')]
                self.collection = await self.sort(*sorting, **kwargs)

            # Paginate resources
            per_page = request.query.get(VAR_PER_PAGE, self.meta.per_page)
            if per_page:
                try:
                    per_page = int(per_page)
                    if per_page:
                        page = int(request.query.get(VAR_PAGE, 0))
                        offset = page * per_page
                        self.collection, total = await self.paginate(request, offset, per_page)
                        headers = make_pagination_headers(
                            request, per_page, page, total, self.meta.page_links)
                except ValueError:
                    raise RESTBadRequest(reason='Pagination params are invalid.')

        response = await super(RESTHandler, self).dispatch(
            request, resource=resource, view=view, **kwargs)
        response.headers.update(headers)
        return response

    async def make_response(self, request, response, **response_kwargs):
        """Convert a handler result to web response."""
        while iscoroutine(response):
            response = await response

        if isinstance(response, StreamResponse):
            return response

        response_kwargs.setdefault('content_type', 'application/json')

        return Response(text=dumps(response), **response_kwargs)

    async def authorize(self, request, **kwargs):
        """Base point for authorization."""
        return True

    async def get_many(self, request, **kwargs):
        """Base point for collect data."""
        return []

    async def get_one(self, request, **kwargs):
        """Load resource."""
        return request.match_info.get(self.name)

    async def filter(self, request, **kwargs):
        """Filter collection."""
        try:
            data = loads(request.query.get(VAR_WHERE))
        except (ValueError, TypeError):
            return self.collection

        self.filters, collection = self.meta.filters.filter(
            data, self.collection, resource=self, **kwargs)

        return collection

    async def sort(self, *sorting, **kwargs):
        """Sort collection."""
        return self.collection

    async def paginate(self, request, offset=0, limit=0):
        """Paginate collection.

        :param request: client's request
        :param offset: current offset
        :param limit: limit items per page
        :returns: (paginated collection, count of resources)
        """
        return self.collection[offset: offset + limit], len(self.collection)

    async def get(self, request, resource=None, **kwargs):
        """Get resource or collection of resources.

        ---
        parameters:
            - name: resource
              in: path
              type: string

        """
        if resource is not None and resource != '':
            return self.to_simple(request, resource, **kwargs)

        return self.to_simple(request, self.collection, many=True, **kwargs)

    def to_simple(self, request, data, many=False, **kwargs):
        """Serialize response to simple object (list, dict)."""
        schema = self.get_schema(request, **kwargs)
        return schema.dump(data, many=many).data if schema else data

    def get_schema(self, request, resource=None, **kwargs):
        """Create schema instance."""
        return self.Schema and self.Schema()

    async def post(self, request, resource=None, **kwargs):
        """Create a resource."""
        resource = await self.load(request, resource=resource, **kwargs)
        resource = await self.save(request, resource=resource, **kwargs)
        return self.to_simple(request, resource, **kwargs)

    async def load(self, request, resource=None, **kwargs):
        """Load resource from given data."""
        schema = self.get_schema(request, resource=resource, **kwargs)
        data = await self.parse(request)
        resource, errors = schema.load(data, partial=resource is not None)
        if errors:
            raise RESTBadRequest(reason='Bad request', json={'errors': errors})
        return resource

    async def save(self, request, resource=None, **kwargs):
        """Create a resource."""
        return resource

    async def put(self, request, resource=None, **kwargs):
        """Update a resource.

        ---
        parameters:
            - name: resource
              in: path
              type: string
        """
        if resource is None:
            raise RESTNotFound(reason='Resource not found')

        return await self.post(request, resource=resource, **kwargs)

    patch = put

    async def delete(self, request, resource=None, **kwargs):
        """Delete a resource."""
        if resource is None:
            raise RESTNotFound(reason='Resource not found')
        self.collection.remove(resource)

    async def batch(self, request):
        """Make group operations."""


def make_pagination_headers(request, limit, curpage, total, links=False):
    """Return Link Hypermedia Header."""
    lastpage = math.ceil(total / limit) - 1
    headers = {'X-Total-Count': str(total), 'X-Limit': str(limit),
               'X-Page-Last': str(lastpage), 'X-Page': str(curpage)}
    if links:
        base = "{}?%s".format(request.path)
        links = {}
        links['first'] = base % urlencode(dict(request.query, **{VAR_PAGE: 0}))
        links['last'] = base % urlencode(dict(request.query, **{VAR_PAGE: lastpage}))
        if curpage:
            links['prev'] = base % urlencode(dict(request.query, **{VAR_PAGE: curpage - 1}))
        if curpage < lastpage:
            links['next'] = base % urlencode(dict(request.query, **{VAR_PAGE: curpage + 1}))
        headers['Link'] = ",".join(['<%s>; rel="%s"' % (v, n) for n, v in links.items()])
    return headers


#  pylama:ignore=W0201
