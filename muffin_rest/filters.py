""" Support admin filters. """

import operator
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
        self.filters = {}
        for field in self._fields.values():
            collection, active = field.flt.filter(collection, self.data)
            if active:
                self.filters[field.flt.column_name] = field.data
        return collection


class Filter:

    """ Implement filters. """

    form_field = wtf.StringField
    default = FilterDefault()
    options = {}
    operations = {
        '==': operator.eq,
        '!=': operator.ne,
        '>=': operator.ge,
        '<=': operator.le,
        '>': operator.gt,
        '<': operator.lt,
    }

    def __init__(self, column_name, filter_name=None, op='==', **options):
        """ Store name and mode. """
        self.column_name = column_name
        self.filter_name = filter_name or column_name
        self.options = options or self.options
        self.op = self.operations.get(op)

    def bind(self, form):
        """ Bind to filter's form. """
        form_field = self.form_field(**self.options)
        form_field = form._fields[self.filter_name] = form_field.bind(
            form, self.filter_name, prefix=form._prefix)
        form_field.flt = self

    def filter(self, collection, data):
        """ Load value and filter collection. """
        value = self.value(data)
        if value is self.default:
            return collection, False
        if self.op is None:
            return collection, True
        return self.apply(collection, value), True

    def value(self, data):
        """ Get value from data. """
        value = data.get(self.filter_name, self.default)
        return value or self.default

    def apply(self, collection, value):
        """ Filter collection. """
        return [o for o in collection if self.op(getattr(o, self.column_name, None), value)]


# Filters for base primitives
BoolFilter = type('BoolFilter', (Filter,), {'form_field': wtf.BooleanField})
IntegerFilter = type('IntegerFilter', (Filter,), {'form_field': wtf.IntegerField})
DateFilter = type('DateFilter', (Filter,), {'form_field': wtf.DateField})
DateTimeFilter = type('DateTimeFilter', (Filter,), {'form_field': wtf.DateTimeField})
ChoiceFilter = type('ChoiceFilter', (Filter,), {'form_field': wtf.SelectField})


def default_converter(handler, flt, fcls=Filter):
    """ Convert column name to filter. """
    if isinstance(flt, Filter):
        return flt

    if isinstance(flt, str):
        flt = (flt,)

    return fcls(*flt)
