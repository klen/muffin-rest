from muffin_rest.peewee import PWRESTHandler

from example import app
from example.forms import ResourceForm
from example.models import ResourceModel


@app.register
class Resource(PWRESTHandler):

    form = ResourceForm
    model = ResourceModel
