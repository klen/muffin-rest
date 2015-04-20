from muffin_rest.peewee import PWRESTHandler

from example import app
from example.models import ResourceModel


@app.register
class Resource(PWRESTHandler):

    model = ResourceModel
