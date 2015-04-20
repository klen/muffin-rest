""" Support Muffin-Peewee. """
import muffin
from muffin_peewee.models import to_simple

from muffin_rest import RESTHandler, RESTHandlerMeta, Form


try:
    from wtfpeewee.orm import model_form
except ImportError:
    model_form = None


class PWRESTHandlerMeta(RESTHandlerMeta):

    """ Peewee specific. """

    def __new__(mcs, name, bases, params):
        """ Prepare handler params. """
        model = params.get('model')
        params.setdefault('name', model and model._meta.db_table.lower() or name.lower())
        cls = super(PWRESTHandlerMeta, mcs).__new__(mcs, name, bases, params)
        if not cls.form and cls.model and model_form:
            cls.form = model_form(cls.model, base_class=Form, **cls.form_meta)
        return cls


class PWRESTHandler(RESTHandler, metaclass=PWRESTHandlerMeta):

    """ Support REST for Peewee. """

    model = None

    # only, exclude, recurse
    simple_meta = {}

    # only, exclude, field_args
    form_meta = {}

    def get_many(self, request):
        """ Get collection. """
        return self.model.select()

    def get_one(self, request):
        """ Load a resource. """
        resource = request.match_info.get(self.name)
        if not resource:
            return None

        try:
            return self.collection.where(self.model._meta.primary_key == resource).get()
        except Exception:
            raise muffin.HTTPNotFound()

    def populate(self):
        """ Create object. """
        return self.model()

    def save_form(self, form, request, **resources):
        """ Save data. """
        resource = yield from super(PWRESTHandler, self).save_form(form, request, **resources)
        resource.save()
        return resource

    def to_simple(self, data, many=False):
        """ Serialize data. """
        if many:
            return super(PWRESTHandler, self).to_simple(data, many)
        return to_simple(data, **self.simple_meta)

    def delete(self, request, **resources):
        """ Delete a resource. """
        resource = resources.get(self.name)
        if not resource:
            raise muffin.HTTPNotFound('Resource not found')
        resource.delete().execute()
