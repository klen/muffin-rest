import datetime as dt

import peewee as pw

from example import db


@db.register
class Category(pw.Model):
    name = pw.CharField()


@db.register
class Pet(pw.Model):

    created = pw.DateTimeField(default=dt.datetime.utcnow)
    name = pw.CharField()
    photoUrls = pw.CharField()
    status = pw.CharField(choices=['available', 'pending', 'sold'])

    category = pw.ForeignKeyField(Category)


# don't do on production, this is only for the example
Category.create_table()
Pet.create_table()
