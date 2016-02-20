"""Handle REST."""
import datetime as dt
from asyncio import iscoroutine
from urllib.parse import urlencode

from aiohttp import MultiDict
from aiohttp.web import StreamResponse, Response
from muffin.handler import Handler, abcoroutine
from ujson import dumps # noqa

from muffin_rest import RESTNotFound, RESTBadRequest, FILTER_PREFIX, default_converter, FilterForm


PAGE_VAR = FILTER_PREFIX + '-page'
LIMIT_VAR = FILTER_PREFIX + '-limit'


class RESTHandler(Handler):

    """Implement a common handler for REST operations."""

    #: A form for create/update the resource
    form = None

    #: Resource filters, it could be a field names or Filter instances
    filters = ()

    #: A function which convert field names to Filters
    filters_converter = default_converter

    #: If greater than zero collection of the resources will be paginated
    limit = 0

    def __init__(self):
        """Initialize a filters' form. And convert filters."""
        self.filters_form = FilterForm(prefix=FILTER_PREFIX)
        for flt in self.filters:
            field = self.filters_converter(flt)
            field.bind(self.filters_form)

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
    def dispatch(self, request, **kwgs):
        """Process request."""
        headers = {}

        # Authorization endpoint
        self.auth = yield from self.authorize(request)

        # Load collection
        self.collection = yield from self.get_many(request)

        if request.method == 'POST':
            return (yield from super(RESTHandler, self).dispatch(request, **kwgs))

        resource = yield from self.get_one(request)

        if request.method == 'GET' and resource is None:

            # Filter the collection
            if self.filters_form._fields:
                self.collection = yield from self.filter(request)

            # Paginate the collection
            try:
                limit = int(request.GET.get(LIMIT_VAR, self.limit))
                if limit:
                    curpage = int(request.GET.get(PAGE_VAR, 0))
                    offset = curpage * limit
                    self.collection, total = yield from self.paginate(request, offset, limit)
                    headers.update(make_pagination_headers(request, limit, curpage, total))
            except ValueError:
                raise RESTBadRequest('Pagination params are invalid.')

        response = yield from super(RESTHandler, self).dispatch(request, resource=resource, **kwgs)
        response.headers.update(headers)
        return response

    @abcoroutine
    def make_response(self, request, response):
        """Convert a handler result to web response."""
        while iscoroutine(response):
            response = yield from response

        if isinstance(response, StreamResponse):
            return response

        return Response(text=dumps(response), content_type='application/json')

    @abcoroutine
    def authorize(self, request):
        """Base point for authorization."""
        return True

    @abcoroutine
    def parse(self, request):
        """Ensure that request.data is multidict."""
        data = yield from super().parse(request)
        if not isinstance(data, MultiDict):
            data = MultiDict(data)
        return data

    @abcoroutine
    def get_many(self, request):
        """Base point for collect data."""
        return []

    @abcoroutine
    def filter(self, request):
        """Filter collection."""
        return self.filters_form.process(self.collection, request.GET)

    @abcoroutine
    def get_one(self, request):
        """Load resource."""
        return request.match_info.get(self.name)

    @abcoroutine
    def get_form(self, request, resource=None):
        """Initialize resource's form."""
        formdata = yield from self.parse(request)

        if not self.form:
            raise RESTBadRequest(reason="%s.form is not defined." % type(self).__name__)

        if resource:
            data = {}
            for name, field, *_ in self.form()._unbound_fields:
                value = getattr(resource, name, None)
                if isinstance(value, (dt.datetime, dt.date)):
                    field = field.bind(None, name, _meta=1)
                    value = value.strftime(field.format)
                data[name] = value

            data.update(formdata)
            formdata = MultiDict(data)

        return self.form(formdata, obj=resource)

    @abcoroutine
    def save_form(self, form, request, resource=None):
        """Save self form."""
        if resource is None:
            resource = self.populate()

        form.populate_obj(resource)
        return resource

    def populate(self):
        """Create a resource."""
        return object()

    def to_simple(self, data, many=False):
        """Serialize response to simple object (list, dict)."""
        if many:
            return [self.to_simple(r) for r in data]
        return str(data)

    @abcoroutine
    def get(self, request, resource=None):
        """Get resource or collection of resources."""
        if resource is not None and resource != '':
            return self.to_simple(resource)

        return self.to_simple(self.collection, many=True)

    @abcoroutine
    def post(self, request):
        """Create a resource."""
        form = yield from self.get_form(request)
        if not form.validate():
            raise RESTBadRequest(json=form.errors)
        resource = yield from self.save_form(form, request)
        return self.to_simple(resource)

    @abcoroutine
    def put(self, request, resource=None):
        """Update a resource."""
        if resource is None:
            raise RESTNotFound(reason='Resource not found')

        form = yield from self.get_form(request, resource=resource)
        if not form.validate():
            raise RESTBadRequest(json=form.errors)
        resource = yield from self.save_form(form, request, resource=resource)
        return self.to_simple(resource)

    patch = put

    @abcoroutine
    def batch(self, request):
        """Make group operations."""

    @abcoroutine
    def delete(self, request, resource=None):
        """Delete a resource."""
        if resource is None:
            raise RESTNotFound(reason='Resource not found')
        self.collection.remove(resource)

    @abcoroutine
    def paginate(self, request, offset=0, limit=0):
        """Paginate collection.

        :param request: client's request
        :param offset: current offset
        :param limit: limit items per page
        :returns: (paginated collection, count of resources)
        """
        return self.collection[offset: offset + limit], len(self.collection)

    @classmethod
    def scheme(cls):
        """Return self schema."""
        return {
            'form': cls.form and {
                name: str(type(field)) for (name, field) in cls.form()._fields.items()} or None,
            'methods': cls.methods,
            'description': cls.__doc__,
        }


def make_pagination_headers(request, limit, curpage, total):
    """Return Link Hypermedia Header."""
    lastpage = total // limit
    headers = {'X-Total-Count': str(total), 'X-Limit': str(limit),
               'X-Page-Last': str(lastpage), 'X-Page': str(curpage)}
    base = "{}?%s".format(request.path)
    links = {}
    links['first'] = base % urlencode(dict(request.GET, **{PAGE_VAR: 0}))
    links['last'] = base % urlencode(dict(request.GET, **{PAGE_VAR: lastpage}))
    if curpage:
        links['prev'] = base % urlencode(dict(request.GET, **{PAGE_VAR: curpage - 1}))
    if curpage < lastpage:
        links['next'] = base % urlencode(dict(request.GET, **{PAGE_VAR: curpage + 1}))

    headers['Link'] = ",".join(['<%s>; rel="%s"' % (v, n) for n, v in links.items()])
    return headers


#  pylama:ignore=W0201
