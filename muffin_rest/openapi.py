"""Create openapi schema from the given API."""
import typing as t
import inspect
import re
from http import HTTPStatus

from apispec import APISpec, yaml_utils, utils
from apispec.ext.marshmallow import MarshmallowPlugin
from http_router.routes import DynamicRoute, Route
from asgi_tools.response import CAST_RESPONSE
from muffin import Response

SKIP_PATH = {'/openapi.json', '/swagger'}
DEFAULT_METHODS = 'get',
RE_URL = re.compile(r'<(?:[^:<>]+:)?([^<>]+)>')
HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT']


def render_openapi(api, request):
    """Prepare openapi specs."""
    # Setup Specs
    options = dict(api.apispec_params)
    options.setdefault('servers', [{
        'url': str(request.url.with_query('').with_path(api.prefix))
    }])

    spec = APISpec(
        options.pop('title', f"{ api.app.name.title() } API"),
        options.pop('version', '1.0.0'),
        options.pop('openapi_version', '3'),
        **options, plugins=[MarshmallowPlugin()])
    spec.tags = {}

    # Setup Authorization
    if api.authorize:
        _, _, schema = parse_docs(api.authorize)
        spec.options['security'] = []
        for key, value in schema.items():
            spec.components.security_scheme(key, value)
            spec.options['security'].append({key: []})

    # Setup Paths
    routes = api.router.routes()
    for route in routes:
        if route.path in SKIP_PATH:
            continue

        #  route_to_spec(route, spec)

        #  cb = route.target
        #  summary, desc, gschema = parse_docs(cb)
        #  is_endpoint = inspect.isclass(cb) and issubclass(cb, Endpoint)
        #  if cb not in tags:
        #      tags[cb] = cb.meta.name if is_endpoint else cb.__name__
        #      spec.tag({'name': tags[cb], 'description': summary})
        #      if is_endpoint and cb.meta.Schema:
        #          spec.components.schema(cb.meta.Schema.__name__, schema=cb.meta.Schema)

        #  parameters = []
        #  if isinstance(route, DynamicRoute):
        #      for param in route.convertors:
        #          parameters.append({'in': 'path', 'name': param})

        #  operations = {}
        #  methods = [m for m in HTTP_METHODS if m in route.methods]
        #  for method in methods or DEFAULT_METHODS:
        #      method = method.lower()

        #      operations[method] = {
        #          'summary': summary,
        #          'description': desc,
        #          'tags': [tags[cb]],
        #      }

        #      if not hasattr(cb, method):
        #          continue

        #      operations[method]['summary'], operations[method]['desc'], schema = parse_docs(
        #          getattr(cb, method)
        #      )
        #      operations[method] = merge_dicts(operations[method], update_operation(cb, method))
        #      if schema:
        #          operations = merge_dicts(operations, schema)

        #  operations = merge_dicts(operations, gschema or {})

        #  #  spec.path(RE_URL.sub('{\1}', route.path), operations=operations)
        spec.path(route.path, **route_to_spec(route, spec))

    return spec.to_dict()


def parse_docs(cb: t.Callable) -> t.Tuple[str, str, t.Dict]:
    """Parse docs from the given callback."""
    docs = cb.__doc__ or ''
    schema = yaml_utils.load_yaml_from_docstring(docs)
    docs = docs.split('---')[0]
    docs = utils.dedent(utils.trim_docstring(docs))
    summary, _, description = docs.partition('\n\n')
    return summary, description.strip(), schema


def merge_dicts(source: t.Dict, merge: t.Dict) -> t.Dict:
    """Merge dicts."""
    result = dict(source)
    result.update({
        key: merge_dicts(source[key], merge[key])
        if isinstance(source.get(key), dict) and isinstance(merge[key], dict)
        else merge[key]
        for key in merge.keys()
    })
    return result


def route_to_spec(route: Route, spec: APISpec) -> t.Dict:
    """Convert the given router to openapi operations."""
    results: t.Dict = {'parameters': [], 'operations': {}}
    if isinstance(route, DynamicRoute):
        for param in route.params:
            results['parameters'].append({'in': 'path', 'name': param})

    if hasattr(route.target, 'openapi'):
        results['operations'] = route.target.openapi(route, spec)
        return results

    cb = route.target
    summary, desc, schema = parse_docs(cb)
    if cb not in spec.tags:
        spec.tags[cb] = cb.__name__
        spec.tag({'name': cb.__name__, 'description': summary})

    responses = return_type_to_response(cb)
    for method in route_to_methods(route):
        results['operations'][method] = {
            'summary': summary,
            'description': desc,
            'tags': [spec.tags[cb]],
            'responses': responses
        }

    results['operations'] = merge_dicts(results['operations'], schema)
    return results


def route_to_methods(route: Route) -> t.List[str]:
    """Get sorted methods from the route."""
    methods = [m for m in HTTP_METHODS if m in route.methods]
    return [m.lower() for m in methods or DEFAULT_METHODS]


def return_type_to_response(fn: t.Callable) -> t.Dict:
    """Generate reponses specs based on the given function's return type."""
    responses = {}
    return_type = fn.__annotations__.get('return')
    return_type = CAST_RESPONSE.get(return_type, return_type)
    if inspect.isclass(return_type) and issubclass(return_type, Response) and \
            return_type.content_type:

        responses[return_type.status_code] = {
            'description': HTTPStatus(return_type.status_code).description,
            'content': {
                return_type.content_type: {
                }
            }
        }
    return responses


def update_operation(cb, method):
    """Update operation for a method."""
    operation = {
        'responses': {
            200: {
                'description': 'Successful Operation',
                'content': {
                    'application/json': {
                    }
                }
            }
        }
    }
    if not cb.meta.Schema:
        return

    schema = {'$ref': f"#/components/schemas/{ cb.meta.Schema.__name__ }"}

    if method in {'post', 'put', 'patch'}:
        operation['requestBody'] = {
            'required': True,
            'content': {
                'application/json': {'schema': schema}
            }
        }

    if method != 'delete':
        operation['responses'][200]['content']['application/json']['schema'] = schema

    return operation
