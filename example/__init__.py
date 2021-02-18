import muffin
import muffin_peewee


app = muffin.Application('rest', debug=True)

db = muffin_peewee.Plugin(app)

# Register the API
from example.api import * # noqa
