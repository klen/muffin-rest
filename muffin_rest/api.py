"""!!! STILL NOT IMPLEMENTED. WORK IN PROGRESS !!!."""
import os.path as op
import re
from types import FunctionType, MethodType

from apispec import APISpec, utils
from copy import deepcopy
from collections import OrderedDict
import muffin
from muffin import Handler
from muffin.app import BaseApplication as Application

from .handlers import RESTHandler


PREFIX_RE = re.compile(r'(/|\s)')
PLUGIN_ROOT = op.dirname(op.abspath(__file__))


class Api():
    """Bind group of resources together."""

    def __init__(self, prefix='/api', swagger=True):
        """Initialize the API."""
        self.prefix = prefix.rstrip('/')
        self.prefix_name = PREFIX_RE.sub('.', prefix.strip('/'))
        self.app = Application()
        self.parent = None
        self.handlers = {}

        # Support Swagger
        if swagger:
            self.app.register('/')(Handler.from_view(self.swagger_ui))
            self.register('/schema.json')(Handler.from_view(self.swagger_schema))

    def bind(self, app):
        """Bind API to Muffin."""
        self.parent = app
        app.add_subapp(self.prefix, self.app)

    def register(self, *paths, methods=None, name=None):
        """Register handler to the API."""
        if isinstance(methods, str):
            methods = [methods]

        def wrapper(handler):

            if isinstance(handler, (FunctionType, MethodType)):
                handler = RESTHandler.from_view(handler, *(methods or ['GET']))

            if handler.name in self.handlers:
                raise muffin.MuffinException('Handler is already registered: %s' % handler.name)

            self.handlers[tuple(paths or ["/{0}/{{{0}}}".format(handler.name)])] = handler

            handler.bind(self.app, *paths, methods=methods, name=name or handler.name)
            return handler

        # Support for @app.register(func)
        if len(paths) == 1 and callable(paths[0]):
            view = paths[0]
            paths = []
            return wrapper(view)

        return wrapper

    def swagger_ui(self, request):
        """Render swagger UI."""
        schema_url = self.prefix + '/schema.json'
        return """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/3.0.10/swagger-ui.css" >
            </head>
            <body>
                <div id="ui"></div>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/3.0.10/swagger-ui-bundle.js"> </script>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/3.0.10/swagger-ui-standalone-preset.js"> </script>
                <script>
                    window.onload = function() {
                        const ui = SwaggerUIBundle({
                            url: "%s",
                            dom_id: '#ui',
                            presets: [
                                SwaggerUIBundle.presets.apis,
                                SwaggerUIStandalonePreset
                            ],
                            plugins: [SwaggerUIBundle.plugins.DownloadUrl],
                            layout: "StandaloneLayout"
                        })
                    window.ui = ui
                }
                </script>
            </body>
            </html>
        """ % schema_url

    def swagger_schema(self, request):
        """Render API Schema."""
        if self.parent is None:
            return {}

        spec = APISpec(
            self.parent.name, self.parent.cfg.get('VERSION', ''),
            plugins=['apispec.ext.marshmallow'], basePatch=self.prefix
        )

        for paths, handler in self.handlers.items():
            spec.add_tag({
                'name': handler.name,
                'description': utils.dedent(handler.__doc__ or ''),
            })
            for path in paths:
                operations = {}
                for http_method in handler.methods:
                    method = getattr(handler, http_method.lower())
                    operation = OrderedDict({
                        'tags': [handler.name],
                        'summary': method.__doc__,
                        'produces': ['application/json'],
                        'responses': {200: {'schema': {'$ref': {'#/definitions/' + handler.name}}}}
                    })
                    operation.update(utils.load_yaml_from_docstring(method.__doc__) or {})
                    operations[http_method.lower()] = operation

                spec.add_path(self.prefix + path, operations=operations)

            if getattr(handler, 'Schema', None):
                kwargs = {}
                if getattr(handler.meta, 'model', None):
                    kwargs['description'] = utils.dedent(handler.meta.model.__doc__ or '')
                spec.definition(handler.name, schema=handler.Schema, **kwargs)

        return deepcopy(spec.to_dict())

#  pylama:ignore=W1401,W0212
