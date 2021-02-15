from muffin_rest.peewee import PeeweeEndpoint

from example import app
from example.models import ResourceModel


@app.register
class Resource(PWRESTHandler):

    model = ResourceModel
