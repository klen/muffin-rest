from wtforms import validators, widgets         # noqa
from wtforms.fields import *                    # noqa
from wtforms.form import Form                   # noqa
from wtforms.validators import ValidationError  # noqa


BooleanField.false_values = BooleanField.false_values + (False,)
