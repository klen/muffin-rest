"""Create openapi schema from the given API."""
import typing as t
import inspect
import re
from http import HTTPStatus

from apispec import APISpec, utils
from apispec.ext.marshmallow import MarshmallowPlugin
from http_router.routes import DynamicRoute, Route
from asgi_tools.response import CAST_RESPONSE
from muffin import Response

try:
    from apispec import yaml_utils
except ImportError:
    yaml_utils = None


SKIP_PATH = {'/openapi.json', '/swagger', '/redoc'}
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

        spec.path(route.path, **route_to_spec(route, spec))

    return spec.to_dict()


def parse_docs(cb: t.Callable) -> t.Tuple[str, str, t.Dict]:
    """Parse docs from the given callback."""
    if yaml_utils is None:
        return '', '', {}

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
    responses: t.Dict[int, t.Dict] = {}
    return_type = fn.__annotations__.get('return')
    return_type = CAST_RESPONSE.get(return_type, return_type)  # type: ignore
    if return_type is None:
        return responses

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
