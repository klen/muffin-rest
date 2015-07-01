""" Support admin filters. """

import wtforms as wtf


FILTER_PREFIX = 'mr-'


class FilterDefault:

    """ Default filters value. """

    def __str__(self):
        """ Nothing here. """
        return ""


class FilterForm(wtf.Form):

    """ Store filters for resource. """

    def process(self, collection, formdata=None, obj=None, data=None, **kwargs):
        """ Filter collection. """
        super(FilterForm, self).process(formdata, obj, data, **kwargs)
        for field in self._fields.values():
            collection = field.flt.filter(collection, self.data)
        return collection


class Filter:

    """ Implement filters. """

    field = wtf.StringField
    default = FilterDefault()
    options = {}

    def __init__(self, name, **options):
        """ Store name and mode. """
        self.name = name
        self.options = options or self.options

    def bind(self, form):
        """ Bind to filter's form. """
        field = self.field(**self.options)
        field = form._fields[self.name] = field.bind(form, self.name, prefix=form._prefix)
        field.flt = self

    def filter(self, collection, data):
        """ Load value and filter collection. """
        value = self.value(data)
        if value is self.default:
            return collection
        return self.apply(collection, value)

    def value(self, data):
        """ Get value from data. """
        value = data.get(self.name, self.default)
        return value or self.default

    def apply(self, collection, value):
        """ Filter collection. """
        return [o for o in collection if getattr(o, self.name, None) == value]


class BoolFilter(Filter):

    """ Boolean filter. """

    field = wtf.BooleanField


class IntegerFilter(Filter):

    """ Integer filter. """

    field = wtf.IntegerField


class ChoiceFilter(Filter):

    """ Boolean filter. """

    field = wtf.SelectField


def default_converter(handler, flt):
    """ Convert column name to filter. """
    if isinstance(flt, Filter):
        return flt
    return Filter(flt)
