import muffin


app = muffin.Application(
    'rest', PLUGINS=['muffin_peewee']
)

from example.api import * # noqa Register API Handlers
