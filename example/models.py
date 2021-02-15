import datetime as dt

import peewee as pw

from example import db


@db.register
class ResourceModel(pw.Model):

    created = pw.DateTimeField(default=dt.datetime.utcnow)
    active = pw.BooleanField(default=True)
    name = pw.CharField(null=False)
