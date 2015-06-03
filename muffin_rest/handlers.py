""" REST support. """
import datetime as dt

import muffin
import ujson as json
from aiohttp import MultiDict
from muffin.handler import Handler, abcoroutine

from muffin_rest import RESTNotFound, RESTBadRequest


class RESTHandler(Handler):

    """ Implement handler for REST operations. """

    form = None

    @classmethod
    def connect(cls, app, *paths, methods=None, name=None, **kwargs):
        """ Connect to the application. """
        if not paths:
            paths = [muffin.sre('/%s(/{%s})?/?' % (cls.name, cls.name))]

        if name is None:
            name = "rest-%s" % cls.name

        if methods is None:
            methods = ['*']

        return super(RESTHandler, cls).connect(app, *paths, methods=methods, name=name, **kwargs)

    @abcoroutine
    def dispatch(self, request):
        """ Process REST. """
        self.auth = yield from self.authorize(request)
        self.collection = yield from self.get_many(request)
        resources = {}
        if request.method != 'POST':
            resource = yield from self.get_one(request)
            resources[self.name] = resource
        return (yield from super(RESTHandler, self).dispatch(request, **resources))

    @abcoroutine
    def authorize(self, request):
        """ Base point for authorization. """
        return True

    @abcoroutine
    def parse(self, request):
        """ Ensure that request.data is multidict. """
        data = yield from super().parse(request)
        if not isinstance(data, MultiDict):
            data = MultiDict(data)
        return data

    @abcoroutine
    def get_many(self, request):
        """ Base point for collect data. """
        return []

    @abcoroutine
    def get_one(self, request):
        """ Base point load resource. """
        return request.match_info.get(self.name)

    @abcoroutine
    def get_form(self, request, **resources):
        """ Base point load resource. """
        resource = resources.get(self.name)
        formdata = yield from self.parse(request)

        if not self.form:
            raise muffin.MuffinException("%s.form is not defined." % type(self).__name__)

        if resource:
            data = {}
            for name, field, *args in (self.form._unbound_fields or self.form()._fields):
                value = getattr(resource, name, None)
                if isinstance(value, (dt.datetime, dt.date)):
                    field = field.bind(None, name, _meta=1)
                    value = value.strftime(field.format)
                data[name] = value

            data.update(formdata)
            formdata = MultiDict(data)

        return self.form(formdata, obj=resource)

    @abcoroutine
    def save_form(self, form, request, **resources):
        """ Save self form. """
        resource = resources.get(self.name, self.populate())
        form.populate_obj(resource)
        return resource

    def populate(self):
        """ Create object. """
        return object()

    def to_simple(self, data, many=False):
        """ Convert resource to simple. """
        if many:
            return [self.to_simple(r) for r in data]
        return str(data)

    @abcoroutine
    def get(self, request, **resources):
        """ Get collection of resources. """
        resource = resources.get(self.name)
        if resource:
            return self.to_simple(resource)
        return self.to_simple(self.collection, True)

    @abcoroutine
    def post(self, request):
        """ Create a resource. """
        form = yield from self.get_form(request)
        if not form.validate():
            raise RESTNotFound(
                text=json.dumps(form.errors), content_type='application/json')
        resource = yield from self.save_form(form, request)
        return self.to_simple(resource)

    @abcoroutine
    def put(self, request, **resources):
        """ Update a resource. """
        resource = resources.get(self.name)
        if not resource:
            raise RESTNotFound(reason='Resource not found')

        form = yield from self.get_form(request, **resources)
        if not form.validate():
            raise RESTBadRequest(
                text=json.dumps(form.errors), content_type='application/json')
        resource = yield from self.save_form(form, request, **resources)
        return self.to_simple(resource)

    patch = put

    @abcoroutine
    def delete(self, request, **resources):
        """ Delete a resource. """
        resource = resources.get(self.name)
        if not resource:
            raise RESTNotFound(reason='Resource not found')
