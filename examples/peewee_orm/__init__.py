"""Muffin-Rest example for Peewee ORM.

To run the example you have to install:

    $ pip install muffin-rest[peewee] uvicorn

Run the example with command:

    $ uvicorn examples.peewee_orm:app

"""

from pathlib import Path

from muffin import Application, ResponseRedirect
from muffin_peewee import Plugin as Peewee


app = Application('rest', debug=True)


@app.route('/')
async def home(request):
    """Redirect to Swagger documentation."""
    return ResponseRedirect('/api/swagger')

db = Peewee(app, connection=f"sqlite+async:///{ Path(__file__).parent.joinpath('db.sqlite')}")

# Register the API
from .api import api # noqa

api.setup(app, prefix='/api')
