""" REST support. """

import asyncio
import ujson as json
import muffin


class RESTHandlerMeta(type(muffin.Handler)):

    """ Check REST handlers. """

    __coros = 'authorize', 'get_many', 'get_one', 'get_form', 'save_form'

    def __new__(mcs, name, bases, params):
        """ Prepare handler params. """
        cls = super(RESTHandlerMeta, mcs).__new__(mcs, name, bases, params)
        for name in mcs.__coros:
            setattr(cls, name, muffin.to_coroutine(getattr(cls, name)))

        return cls


class RESTHandler(muffin.Handler, metaclass=RESTHandlerMeta):

    """ Implement handler for REST operations. """

    form = None

    @classmethod
    def connect(cls, app, *paths, name=None):
        """ Connect to the application. """
        if not paths:
            paths = [muffin.sre('/%s(/{%s})?/?' % (cls.name, cls.name))]
        return super(RESTHandler, cls).connect(app, *paths, name=name)

    @asyncio.coroutine
    def dispatch(self, request):
        """ Process REST. """
        self.auth = yield from self.authorize(request)
        self.collection = yield from self.get_many(request)
        resources = {}
        if request.method != 'POST':
            resource = yield from self.get_one(request)
            resources[self.name] = resource
        return (yield from super(RESTHandler, self).dispatch(request, **resources))

    def authorize(self, request):
        """ Base point for authorization. """
        return True

    def get_many(self, request):
        """ Base point for collect data. """
        return []

    def get_one(self, request):
        """ Base point load resource. """
        return request.match_info.get(self.name)

    def get_form(self, request, **resources):
        """ Base point load resource. """
        formdata = yield from self.parse(request)
        resource = resources.get(self.name)

        if not self.form:
            raise muffin.MuffinException("%s.form is not defined." % type(self))

        return self.form(formdata, obj=resource)

    def populate(self):
        """ Create object. """
        return object()

    def save_form(self, form, request, **resources):
        """ Save self form. """
        resource = resources.get(self.name, self.populate())
        form.populate_obj(resource)
        return resource

    def to_simple(self, data, many=False):
        """ Convert resource to simple. """
        if many:
            return [self.to_simple(r) for r in data]
        return str(data)

    def get(self, request, **resources):
        """ Get collection of resources. """
        resource = resources.get(self.name)
        if resource:
            return self.to_simple(resource)
        return self.to_simple(self.collection, True)

    def post(self, request):
        """ Create a resource. """
        form = yield from self.get_form(request)
        if not form.validate():
            raise muffin.HTTPBadRequest(
                text=json.dumps(form.errors), content_type='application/json')
        resource = yield from self.save_form(form, request)
        return self.to_simple(resource)

    def put(self, request, **resources):
        """ Update a resource. """
        resource = resources.get(self.name)
        if not resource:
            raise muffin.HTTPNotFound('Resource not found')

        form = yield from self.get_form(request, **resources)
        if not form.validate():
            raise muffin.HTTPBadRequest(
                text=json.dumps(form.errors), content_type='application/json')
        resource = yield from self.save_form(form, request, **resources)
        return self.to_simple(resource)

    patch = put

    def delete(self, request, **resources):
        """ Delete a resource. """
        resource = resources.get(self.name)
        if not resource:
            raise muffin.HTTPNotFound('Resource not found')
