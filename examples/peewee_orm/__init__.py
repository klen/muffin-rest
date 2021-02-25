from pathlib import Path

import muffin
import muffin_peewee


app = muffin.Application('rest', debug=True)


@app.route('/')
async def home(request):
    """Redirect to Swagger documentation."""
    return muffin.ResponseRedirect('/api/swagger')

db = muffin_peewee.Plugin(
    app, connection=f"sqlite:///{ Path(__file__).parent.joinpath('db.sqlite')}")

# Register the API
from .api import api # noqa

api.setup(app, prefix='/api')
