import muffin
import pytest


@pytest.fixture(params=[
    pytest.param('asyncio'),
    pytest.param('trio'),
], autouse=True)
def anyio_backend(request):
    return request.param


@pytest.fixture
def app():
    app = muffin.Application('muffin-rest', debug=True)

    @app.route('/')
    async def index(request):
        return 'OK'

    return app
