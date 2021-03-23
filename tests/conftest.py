import muffin
import pytest


@pytest.fixture(params=[
    pytest.param(('asyncio', {'use_uvloop': False}), id='asyncio'),
    pytest.param('trio'),
    pytest.param('curio'),
], autouse=True)
def aiolib(request):
    return request.param


@pytest.fixture
def app():
    app = muffin.Application(debug=True)

    @app.route('/')
    async def index(request):
        return 'OK'

    return app
