"""Create openapi schema from the given API."""
from __future__ import annotations

import inspect
import re
from contextlib import suppress
from functools import partial
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Tuple, cast

from apispec import utils
from apispec.core import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from asgi_tools.response import CAST_RESPONSE
from asgi_tools.types import TJSON
from http_router.routes import DynamicRoute, Route
from muffin import Response

from . import LIMIT_PARAM, OFFSET_PARAM

if TYPE_CHECKING:
    from .options import RESTOptions

with suppress(ImportError):
    from apispec import yaml_utils

locals().setdefault("yaml_utils", None)


DEFAULT_METHODS = ("get",)
HTTP_METHODS = [
    "GET",
    "POST",
    "PUT",
    "PATH",
    "DELETE",
    "HEAD",
    "OPTIONS",
    "TRACE",
    "CONNECT",
]
RE_URL = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")  # TODO: Not used
SKIP_PATH = {"/openapi.json", "/swagger", "/redoc"}


def render_openapi(api, request=None):
    """Prepare openapi specs."""
    # Setup Specs
    options = dict(api.openapi_options)
    if request:
        options.setdefault(
            "servers",
            [{"url": str(request.url.with_query("").with_path(api.prefix))}],
        )

    spec = APISpec(
        options["info"].pop("title", f"{ api.app.cfg.name.title() } API"),
        options["info"].pop("version", "1.0.0"),
        options.pop("openapi_version", "3.0.3"),
        **options,
        plugins=[MarshmallowPlugin()],
    )
    tags = {}

    # Setup Authorization
    if api.authorize:
        _, _, schema = parse_docs(api.authorize)
        spec.options["security"] = []
        for key, value in schema.items():
            spec.components.security_scheme(key, value)
            spec.options["security"].append({key: []})

    # Setup Paths
    routes = api.router.routes()
    for route in routes:
        if route.path in SKIP_PATH:
            continue

        spec.path(route.path, **route_to_spec(route, spec, tags))

    return spec.to_dict()


def route_to_spec(route: Route, spec: APISpec, tags: Dict) -> Dict:
    """Convert the given router to openapi operations."""
    results: Dict[str, Any] = {"parameters": [], "operations": {}}
    if isinstance(route, DynamicRoute):
        for param in route.params:
            results["parameters"].append({"in": "path", "name": param})

    target = cast(Callable, route.target)
    if isinstance(target, partial):
        target = target.func

    if hasattr(target, "openapi"):
        results["operations"] = target.openapi(route, spec, tags)
        return results

    summary, desc, schema = parse_docs(target)
    responses = return_type_to_response(target)
    for method in route_to_methods(route):
        results["operations"][method] = {
            "summary": summary,
            "description": desc,
            "responses": responses,
        }

    results["operations"] = merge_dicts(results["operations"], schema)
    return results


def parse_docs(cb: Callable) -> Tuple[str, str, Dict]:
    """Parse docs from the given callback."""
    if yaml_utils is None:
        return "", "", {}

    docs = cb.__doc__ or ""
    schema = yaml_utils.load_yaml_from_docstring(docs)
    docs = docs.split("---")[0]
    docs = utils.dedent(utils.trim_docstring(docs))
    summary, _, description = docs.partition("\n\n")
    return summary, description.strip(), schema


def merge_dicts(source: Dict, merge: Dict) -> Dict:
    """Merge dicts."""
    return dict(
        source,
        **{
            key: (
                (
                    merge_dicts(source[key], merge[key])
                    if isinstance(source[key], dict) and isinstance(merge[key], dict)
                    else (
                        source[key] + merge[key]
                        if isinstance(source[key], list) and isinstance(merge[key], list)
                        else merge[key]
                    )
                )
                if key in source
                else merge[key]
            )
            for key in merge
        },
    )


def route_to_methods(route: Route) -> List[str]:
    """Get sorted methods from the route."""
    methods = [m for m in HTTP_METHODS if m in (route.methods or [])]
    return [m.lower() for m in methods or DEFAULT_METHODS]


def return_type_to_response(fn: Callable) -> Dict:
    """Generate reponses specs based on the given function's return type."""
    responses: Dict[int, Dict] = {}
    return_type = fn.__annotations__.get("return")
    if return_type is None:
        return responses

    return_type = CAST_RESPONSE.get(return_type, return_type)
    if return_type is None:
        return responses

    if (
        inspect.isclass(return_type)
        and issubclass(return_type, Response)
        and return_type.content_type
    ):
        responses[return_type.status_code] = {
            "description": HTTPStatus(return_type.status_code).description,
            "content": {return_type.content_type: {}},
        }
    return responses


class OpenAPIMixin:
    """Render an endpoint to openapi specs."""

    meta: RESTOptions

    @classmethod
    def openapi(cls, route: Route, spec: APISpec, tags: Dict) -> Dict:  # noqa: C901
        """Get openapi specs for the endpoint."""
        meta = cls.meta
        if getattr(meta, meta.base_property, None) is None:
            return {}

        operations: Dict = {}
        summary, desc, schema = parse_docs(cls)
        if cls not in tags:
            tags[cls] = meta.name
            spec.tag({"name": meta.name, "description": summary})
            schema_cls = meta.Schema
            if schema_cls.__name__ not in spec.components.schemas:
                spec.components.schema(meta.Schema.__name__, schema=meta.Schema)

        schema_ref = {"$ref": f"#/components/schemas/{ meta.Schema.__name__ }"}
        for method in route_to_methods(route):
            operations[method] = {"tags": [tags[cls]]}
            is_resource_route = isinstance(route, DynamicRoute) and route.params.get(
                meta.name_id,
            )

            if method == "get" and not is_resource_route:
                operations[method]["parameters"] = []
                if meta.sorting:
                    operations[method]["parameters"].append(meta.sorting.openapi)

                if meta.filters:
                    operations[method]["parameters"].append(meta.filters.openapi)

                if meta.limit:
                    operations[method]["parameters"].append(
                        {
                            "name": LIMIT_PARAM,
                            "in": "query",
                            "schema": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": meta.limit,
                            },
                            "description": "The number of items to return",
                        },
                    )
                    operations[method]["parameters"].append(
                        {
                            "name": OFFSET_PARAM,
                            "in": "query",
                            "schema": {"type": "integer", "minimum": 0},
                            "description": "The offset of items to return",
                        },
                    )

            # Update from the method
            meth = getattr(cls, method, None)
            if isinstance(route.target, partial) and "__meth__" in route.target.keywords:
                meth = getattr(cls, route.target.keywords["__meth__"], None)

            elif method in {"post", "put"}:
                operations[method]["requestBody"] = {
                    "required": True,
                    "content": {"application/json": {"schema": schema_ref}},
                }

            if meth:
                (operations[method]["summary"], operations[method]["description"], mschema) = (
                    parse_docs(meth)
                )
                return_type = meth.__annotations__.get("return")
                if return_type in ("JSONType", TJSON):
                    responses = {
                        200: {
                            "description": "Request is successfull",
                            "content": {"application/json": {"schema": schema_ref}},
                        },
                    }
                else:
                    responses = return_type_to_response(meth)

                operations[method]["responses"] = responses
                operations[method] = merge_dicts(operations[method], mschema)

        return merge_dicts(operations, schema)
