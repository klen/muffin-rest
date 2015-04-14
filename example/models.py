import peewee as pw

from example import app


@app.ps.peewee.register
class ResourceModel(app.ps.peewee.TModel):

    active = pw.BooleanField(default=True)
    name = pw.CharField(null=False)
