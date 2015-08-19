""" Support Muffin-Peewee. """
import peewee as pw
from muffin_peewee.models import to_simple
from wtforms import fields as f

from muffin_rest import RESTHandler, Form, RESTNotFound, Filter, default_converter


try:
    from wtfpeewee.orm import model_form, ModelConverter

    ModelConverter.defaults[pw.DateField] = f.DateField
    ModelConverter.defaults[pw.DateTimeField] = f.DateTimeField

    from muffin_peewee.fields import JSONField

    ModelConverter.defaults[JSONField] = f.TextAreaField

except ImportError:
    model_form = None


def pw_converter(handler, flt):
    """ Convert column name to filter. """
    return default_converter(handler, flt, PWFilter)


class PWRESTHandlerMeta(type(RESTHandler)):

    """ Peewee specific. """

    def __new__(mcs, name, bases, params):
        """ Prepare handler params. """
        model = params.get('model')
        params.setdefault('name', model and model._meta.db_table.lower() or name.lower())
        params.setdefault('model_pk', model and model._meta.primary_key or None)
        cls = super(PWRESTHandlerMeta, mcs).__new__(mcs, name, bases, params)
        if not cls.form and cls.model and model_form:
            cls.form = model_form(cls.model, base_class=Form, **cls.form_meta)
        return cls


class PWRESTHandler(RESTHandler, metaclass=PWRESTHandlerMeta):

    """ Support REST for Peewee. """

    filters_converter = pw_converter

    model = None
    model_pk = None

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
            return self.collection.where(self.model_pk == resource).get()
        except Exception:
            raise RESTNotFound(reason='Resource not found.')

    def populate(self):
        """ Create object. """
        return self.model()

    def save_form(self, form, request, resource=None):
        """ Save data. """
        resource = yield from super(PWRESTHandler, self).save_form(
            form, request, resource=resource)
        resource.save()
        return resource

    def to_simple(self, data, many=False):
        """ Serialize data. """
        if many:
            return super(PWRESTHandler, self).to_simple(data, many)
        return to_simple(data, **self.simple_meta)

    def delete(self, request, resource=None):
        """ Delete a resource. """
        if resource is None:
            raise RESTNotFound(reason='Resource not found')
        resource.delete_instance()


class PWFilter(Filter):

    """ Base filter for Peewee handlers. """

    operations = dict(Filter.operations, **{
        '%': lambda a, b: a % b,
        '<<': lambda a, b: a << b,
    })

    def apply(self, query, value):
        """ Filter a query. """
        form_field = query.model_class._meta.fields.get(self.column_name)
        if not form_field:
            return query
        return query.where(self.op(form_field, value))


class PWMultiField(f.StringField):

    """ Support many values. """

    def process_formdata(self, valuelist):
        """ Save multivalues. """
        self.data = valuelist


class PWMultiFilter(PWFilter):

    """ Support multi values. """

    form_field = PWMultiField

    def apply(self, query, value):
        """ Filter a query. """
        form_field = query.model_class._meta.fields.get(self.column_name)
        if not form_field:
            return query

        return query.where(form_field << value)


class PWLikeFilter(PWFilter):

    """ Filter query by value. """

    def apply(self, query, value):
        """ Filter a query. """
        form_field = query.model_class._meta.fields.get(self.column_name)
        value = "*%s*" % value
        return query.where(form_field % value)
