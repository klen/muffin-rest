import muffin
import muffin_peeewee


app = muffin.Application('rest')

db = muffin_peeewee.Plugin(app)

# Register the API
from example.api import * # noqa
