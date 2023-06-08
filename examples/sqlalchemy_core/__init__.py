"""Muffin-Rest example for SQLAlchemy ORM.

To run the example you have to install:

    $ pip install muffin-rest[sqlalchemy] uvicorn

Run the example with command:

    $ uvicorn examples.sqlalchemy_core:app

"""
from pathlib import Path

import muffin
import muffin_databases

DB_PATH = Path(__file__).parent.parent.absolute() / "db.sqlite"

app: muffin.Application = muffin.Application("rest", debug=True)


@app.route("/")
async def home(request):
    """Redirect to Swagger documentation."""
    return muffin.ResponseRedirect("/api/swagger")


db: muffin_databases.Plugin = muffin_databases.Plugin(app, url=f"sqlite:///{ DB_PATH }")

# Register the API
from .api import api  # noqa: E402

api.setup(app, prefix="/api")
