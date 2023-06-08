import datetime as dt

import peewee as pw

from . import app, db


@db.register
class Category(pw.Model):
    name = pw.CharField()


@db.register
class Pet(pw.Model):
    created = pw.DateTimeField(default=dt.datetime.utcnow)
    name = pw.CharField()
    image = pw.CharField(null=True)
    status = pw.CharField(
        choices=[("available", "available"), ("pending", "pending"), ("sold", "sold")]
    )

    category = pw.ForeignKeyField(Category)


# don't do on production, this is only for the example propouse
@app.on_startup
async def create_schema():
    with db.manager.allow_sync():
        Category.create_table()
        Pet.create_table()
