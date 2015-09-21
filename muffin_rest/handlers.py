"""Handle REST."""
import datetime as dt

import muffin
from aiohttp import MultiDict
from muffin.handler import Handler, abcoroutine

from muffin_rest import RESTNotFound, RESTBadRequest, FILTER_PREFIX, default_converter, FilterForm


class RESTHandler(Handler):

    """Implement a handler for REST operations."""

    form = None
    filters = ()
    filters_converter = default_converter

    def __init__(self):
        """Initialize filters."""
        # Process filters
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
            paths = [muffin.sre('/%s(/{%s})?/?' % (cls.name, cls.name))]

        if name is None:
            name = "rest-%s" % cls.name

        return super(RESTHandler, cls).connect(app, *paths, methods=methods, name=name, **kwargs)

    @abcoroutine
    def dispatch(self, request, view=None):
        """Process request."""
        self.auth = yield from self.authorize(request)
        self.collection = yield from self.get_many(request)

        if request.method == 'POST':
            return (yield from super(RESTHandler, self).dispatch(request, view=view))

        resource = yield from self.get_one(request)

        # Filter collection
        if request.method == 'GET' and resource is None:
            self.collection = yield from self.filter(request)

        return (
            yield from super(RESTHandler, self).dispatch(request, resource=resource, view=view))

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
        if resource:
            return self.to_simple(resource)

        return self.to_simple(self.collection, True)

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
    def delete(self, request, resource=None):
        """Delete a resource."""
        if resource is None:
            raise RESTNotFound(reason='Resource not found')

    @classmethod
    def scheme(cls):
        """Return self schema."""
        return {
            'form': cls.form and {
                name: str(type(field)) for (name, field) in cls.form()._fields.items()} or None,
            'methods': cls.methods,
            'description': cls.__doc__,
        }

#  pylama:ignore=W0201
