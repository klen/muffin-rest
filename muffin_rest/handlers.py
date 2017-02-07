"""REST Handler."""
import math
from asyncio import iscoroutine
from urllib.parse import urlencode

from aiohttp.web import StreamResponse, Response
from muffin.handler import Handler, abcoroutine
from ujson import dumps, loads # noqa

from muffin_rest import RESTNotFound, RESTBadRequest, Filters


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
    def connect(cls, app, *paths, methods=None, name=None, **kwargs):
        """Connect to the application.

        Generate URL, name if it's not provided.
        """
        if not paths:
            paths = ['/%s(/{%s})?/?' % (cls.name, cls.name)]

        if name is None:
            name = "rest.%s" % cls.name

        return super(RESTHandler, cls).connect(app, *paths, methods=methods, name=name, **kwargs)

    @abcoroutine
    def dispatch(self, request, **kwargs):
        """Process request."""
        # Authorization endpoint
        self.auth = yield from self.authorize(request, **kwargs)  # noqa

        # Load collection
        self.collection = yield from self.get_many(request, **kwargs)

        if request.method == 'POST':
            return (yield from super(RESTHandler, self).dispatch(request, **kwargs))

        # Load resource
        resource = yield from self.get_one(request, **kwargs)

        headers = {}

        if request.method == 'GET' and resource is None:

            # Filter resources
            if VAR_WHERE in request.GET:
                self.collection = yield from self.filter(request, **kwargs)

            # Sort resources
            if VAR_SORT in request.GET:
                sorting = [(name.strip('-'), name.startswith('-'))
                           for name in request.GET[VAR_SORT].split(',')]
                self.collection = self.sort(*sorting, **kwargs)

            # Paginate resources
            per_page = request.GET.get(VAR_PER_PAGE, self.meta.per_page)
            if per_page:
                try:
                    per_page = int(per_page)
                    if per_page:
                        page = int(request.GET.get(VAR_PAGE, 0))
                        offset = page * per_page
                        self.collection, total = yield from self.paginate(
                            request, offset, per_page)
                        headers = make_pagination_headers(request, per_page, page, total)
                except ValueError:
                    raise RESTBadRequest(reason='Pagination params are invalid.')

        response = yield from super(RESTHandler, self).dispatch(
            request, resource=resource, **kwargs)
        response.headers.update(headers)
        return response

    @abcoroutine
    def make_response(self, request, response, **response_kwargs):
        """Convert a handler result to web response."""
        while iscoroutine(response):
            response = yield from response

        if isinstance(response, StreamResponse):
            return response

        response_kwargs.setdefault('content_type', 'application/json')

        return Response(text=dumps(response), **response_kwargs)

    @abcoroutine
    def authorize(self, request, **kwargs):
        """Base point for authorization."""
        return True

    @abcoroutine
    def get_many(self, request, **kwargs):
        """Base point for collect data."""
        return []

    @abcoroutine
    def get_one(self, request, **kwargs):
        """Load resource."""
        return request.match_info.get(self.name)

    @abcoroutine
    def filter(self, request, **kwargs):
        """Filter collection."""
        try:
            data = loads(request.GET.get(VAR_WHERE))
        except (ValueError, TypeError):
            return None, self.collection

        self.filters, collection = self.meta.filters.filter(
            data, self.collection, resource=self, **kwargs)

        return collection

    @abcoroutine
    def sort(self, *sorting, **kwargs):
        """Sort collection."""
        return self.collection

    @abcoroutine
    def paginate(self, request, offset=0, limit=0):
        """Paginate collection.

        :param request: client's request
        :param offset: current offset
        :param limit: limit items per page
        :returns: (paginated collection, count of resources)
        """
        return self.collection[offset: offset + limit], len(self.collection)

    @abcoroutine
    def get(self, request, resource=None, **kwargs):
        """Get resource or collection of resources."""
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

    @abcoroutine
    def post(self, request, resource=None, **kwargs):
        """Create a resource."""
        resource = yield from self.load(request, resource=resource, **kwargs)
        resource = yield from self.save(request, resource=resource, **kwargs)
        return self.to_simple(request, resource, **kwargs)

    @abcoroutine
    def load(self, request, resource=None, **kwargs):
        """Load resource from given data."""
        schema = self.get_schema(request, resource=resource, **kwargs)
        data = yield from self.parse(request)
        resource, errors = schema.load(data, partial=resource is not None)
        if errors:
            raise RESTBadRequest(reason='Bad request', json={'errors': errors})
        return resource

    @abcoroutine
    def save(self, request, resource=None, **kwargs):
        """Create a resource."""
        return resource

    @abcoroutine
    def put(self, request, resource=None, **kwargs):
        """Update a resource."""
        if resource is None:
            raise RESTNotFound(reason='Resource not found')

        return (yield from self.post(request, resource=resource, **kwargs))

    patch = put

    @abcoroutine
    def delete(self, request, resource=None, **kwargs):
        """Delete a resource."""
        if resource is None:
            raise RESTNotFound(reason='Resource not found')
        self.collection.remove(resource)

    @abcoroutine
    def batch(self, request):
        """Make group operations."""


def make_pagination_headers(request, limit, curpage, total):
    """Return Link Hypermedia Header."""
    lastpage = math.ceil(total / limit) - 1
    headers = {'X-Total-Count': str(total), 'X-Limit': str(limit),
               'X-Page-Last': str(lastpage), 'X-Page': str(curpage)}
    base = "{}?%s".format(request.path)
    links = {}
    links['first'] = base % urlencode(dict(request.GET, **{VAR_PAGE: 0}))
    links['last'] = base % urlencode(dict(request.GET, **{VAR_PAGE: lastpage}))
    if curpage:
        links['prev'] = base % urlencode(dict(request.GET, **{VAR_PAGE: curpage - 1}))
    if curpage < lastpage:
        links['next'] = base % urlencode(dict(request.GET, **{VAR_PAGE: curpage + 1}))

    headers['Link'] = ",".join(['<%s>; rel="%s"' % (v, n) for n, v in links.items()])
    return headers


#  pylama:ignore=W0201
