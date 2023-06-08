"""Muffin-Rest example for Peewee ORM.

To run the example you have to install:

    $ pip install muffin-rest[peewee] uvicorn

Run the example with command:

    $ uvicorn examples.peewee_orm:app

"""

from pathlib import Path

from muffin import Application, ResponseRedirect
from muffin_peewee import Plugin as Peewee

DB_PATH = Path(__file__).parent.parent / "db.sqlite"

app: Application = Application("rest", debug=True)


@app.route("/")
async def home(request):
    """Redirect to Swagger documentation."""
    return ResponseRedirect("/api/swagger")


db: Peewee = Peewee(app, connection=f"aiosqlite:////{ DB_PATH }")

# Register the API
from .api import api  # noqa: E402

api.setup(app, prefix="/api")
