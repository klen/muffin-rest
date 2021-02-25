import muffin
import muffin_peewee


app = muffin.Application('rest', debug=True)

@app.route('/')
async def home(request):
    return muffin.ResponseRedirect('/api/swagger')

db = muffin_peewee.Plugin(app)

# Register the API
from example.api import api

api.setup(app, prefix='/api')
