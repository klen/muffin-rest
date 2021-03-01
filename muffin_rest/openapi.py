"""Create openapi schema from the given API."""
import typing as t
import inspect
import re
from http import HTTPStatus
from functools import partial

from apispec import APISpec, utils
from apispec.ext.marshmallow import MarshmallowPlugin
from http_router.routes import DynamicRoute, Route
from asgi_tools.response import CAST_RESPONSE
from muffin import Response

try:
    from apispec import yaml_utils
except ImportError:
    yaml_utils = None


DEFAULT_METHODS = 'get',
HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT']
RE_URL = re.compile(r'<(?:[^:<>]+:)?([^<>]+)>')
SKIP_PATH = {'/openapi.json', '/swagger', '/redoc'}


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
    return dict(source, **{
        key: ((
            merge_dicts(source[key], merge[key])
            if isinstance(source[key], dict) and isinstance(merge[key], dict)
            else (
                source[key] + merge[key]
                if isinstance(source[key], list) and isinstance(merge[key], list)
                else merge[key]
            )
        ) if key in source else merge[key]) for key in merge})


def route_to_spec(route: Route, spec: APISpec) -> t.Dict:
    """Convert the given router to openapi operations."""
    results: t.Dict = {'parameters': [], 'operations': {}}
    if isinstance(route, DynamicRoute):
        for param in route.params:
            results['parameters'].append({'in': 'path', 'name': param})

    target = route.target
    if isinstance(target, partial):
        target = target.func

    if hasattr(target, 'openapi'):
        results['operations'] = target.openapi(route, spec)
        return results

    summary, desc, schema = parse_docs(target)
    responses = return_type_to_response(target)
    for method in route_to_methods(route):
        results['operations'][method] = {
            'summary': summary,
            'description': desc,
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
