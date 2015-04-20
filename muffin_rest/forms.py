""" Update WTForms for REST. """
import datetime as dt

from wtforms import validators, widgets         # noqa
from wtforms.fields import *                    # noqa
from wtforms.form import Form as WTForm
from wtforms.validators import ValidationError  # noqa


BooleanField.false_values = BooleanField.false_values + (False,)


class MultiDict(dict):

    """ Muttable multidict. """

    def getlist(self, key):
        """ Implement method. """
        val = self[key]
        if not isinstance(val, list):
            val = [val]
        return val

    def getall(self, key):
        """ Implement method. """
        return [self[key]]


class Form(WTForm):

    """ Supports partitial updates. """

    def __init__(self, formdata=None, obj=None, prefix='', data=None, meta=None, **kwargs):
        """ Convert formdata to multidict. """
        if formdata is not None:
            formdata = MultiDict(formdata)

        super(Form, self).__init__(formdata, obj, prefix, data, meta, **kwargs)

    def process(self, formdata=None, obj=None, data=None, **kwargs):
        """ Fill formdata from object. And support `process_field` method. """
        for name in self._fields:
            if name in formdata:
                if hasattr(self, 'process_%s' % name):
                    formdata[name] = getattr(self, 'process_%s' % name)(formdata[name])
            elif obj:
                value = getattr(obj, name, None)
                field = self._fields[name]
                if value is not None:
                    if isinstance(value, (dt.datetime, dt.date)):
                        value = value.strftime(field.format)

                    formdata[name] = value

        super(Form, self).process(formdata, obj, data, **kwargs)
