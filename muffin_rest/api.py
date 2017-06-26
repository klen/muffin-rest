"""!!! STILL NOT IMPLEMENTED. WORK IN PROGRESS !!!."""
import os.path as op
import re
from types import FunctionType

from apispec import APISpec, utils
from copy import deepcopy
from collections import OrderedDict
import muffin


PREFIX_RE = re.compile('(/|\s)')
PLUGIN_ROOT = op.dirname(op.abspath(__file__))


class Api():
    """Bind group of resources together."""

    def __init__(self, app, prefix='/api', swagger=True):
        """Initialize the API."""
        self.app = app
        self.prefix = prefix.rstrip('/')
        self.prefix_name = PREFIX_RE.sub('.', prefix.strip('/'))
        self.handlers = {}
        self.resource = muffin.urls.ParentResource(self.prefix, name=self.prefix_name)
        self.app.router._reg_resource(self.resource)
        if swagger:
            app.ps.jinja2.cfg.template_folders.append(op.join(PLUGIN_ROOT, 'templates'))
            app.register(self.prefix)(muffin.Handler.from_view(self.swagger_ui, 'GET'))
            app.register(self.prefix + '/schema.json')(
                muffin.Handler.from_view(self.swagger_schema, 'GET'))

    def register(self, *paths, methods=None, name=None):
        """Register handler to the API."""
        if isinstance(methods, str):
            methods = [methods]

        def wrapper(handler):

            if isinstance(handler, FunctionType):
                handler = muffin.Handler.from_view(handler, *(methods or ['GET']))

            if handler.name in self.handlers:
                raise muffin.MuffinException('Handler is already registered: %s' % handler.name)

            self.handlers[tuple(paths or ["/{0}/{{{0}}}".format(handler.name)])] = handler

            handler.connect(
                self.app, *paths, methods=methods, name=name or handler.name,
                router=self.resource.router)

            return handler

        # Support for @app.register(func)
        if len(paths) == 1 and callable(paths[0]):
            view = paths[0]
            paths = []
            return wrapper(view)

        return wrapper

    def swagger_ui(self, request):
        """Render swagger UI."""
        return self.app.ps.jinja2.render('swagger.html', schema_url=self.prefix + '/schema.json')

    def swagger_schema(self, request):
        """Render API Schema."""
        spec = APISpec(
            self.app.name, self.app.cfg.VERSION, plugins=['apispec.ext.marshmallow'],
            basePatch=self.prefix
        )

        for paths, handler in self.handlers.items():
            spec.add_tag({
                'name': handler.name,
                'description': utils.dedent(handler.__doc__ or ''),
            })
            for path in paths:
                operations = {}
                for method in handler.methods:
                    method = getattr(handler, method.lower())
                    operation = OrderedDict({
                        'tags': [handler.name],
                        'summary': method.__doc__,
                        'produces': ['application/json'],
                        'responses': {200: {'schema': {'$ref': {'#/definitions/' + handler.name}}}}
                    })
                    operation.update(utils.load_yaml_from_docstring(method.__doc__) or {})
                    operations[method.__name__] = operation

                spec.add_path(self.prefix + path, operations=operations)

            if handler.Schema:
                kwargs = {}
                if handler.meta.model:
                    kwargs['description'] = utils.dedent(handler.meta.model.__doc__)
                spec.definition(handler.name, schema=handler.Schema, **kwargs)

        return deepcopy(spec.to_dict())

#  pylama:ignore=W1401,W0212
