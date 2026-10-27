"""Create openapi schema from the given API."""

from __future__ import annotations

import inspect
from contextlib import suppress
from functools import partial
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Callable, cast

from apispec import utils
from apispec.core import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from asgi_tools.response import CAST_RESPONSE
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
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
    "TRACE",
    "CONNECT",
]
SKIP_PATH = {"/openapi.json", "/swagger", "/redoc"}


def render_openapi(api, request=None):
    """Prepare openapi specs."""
    spec = _cached_spec(api)
    result = spec.to_dict()
    if request and "servers" not in api.openapi_options:
        result["servers"] = [{"url": str(request.url.with_query("").with_path(api.prefix))}]
    return result


def _cached_spec(api) -> APISpec:
    """Build the spec once per route set.

    shortcut: routes are keyed by path+methods, so editing a handler without
    re-registering its route is not detected; rebuild on any route change.
    """
    routes = api.router.routes()
    key = tuple((route.path, tuple(sorted(route.methods or ()))) for route in routes)
    spec = getattr(api, "_openapi_spec", None)
    if spec is not None and api._openapi_spec_key == key:
        return spec

    spec = _build_spec(api, routes)
    api._openapi_spec = spec
    api._openapi_spec_key = key
    return spec


def _build_spec(api, routes) -> APISpec:
    """Build the APISpec from the API options and routes."""
    options = dict(api.openapi_options)
    info = dict(options["info"])
    title = info.pop("title", None)
    if title is None:
        title = f"{api.app.cfg.name.title()} API"
    version = info.pop("version", None)
    if version is None:
        version = "1.0.0"
    options["info"] = info

    spec = APISpec(
        title,
        version,
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
    for route in routes:
        if route.path in SKIP_PATH:
            continue

        spec.path(route.path, **route_to_spec(route, spec, tags))

    return spec


def route_to_spec(route: Route, spec: APISpec, tags: dict) -> dict:
    """Convert the given router to openapi operations."""
    results: dict[str, Any] = {"parameters": [], "operations": {}}
    if isinstance(route, DynamicRoute):
        for param in route.params:
            results["parameters"].append(
                {"in": "path", "name": param, "required": True, "schema": {"type": "string"}},
            )

    target = cast("Callable", route.target)
    if isinstance(target, partial):
        target = target.func

    if hasattr(target, "openapi"):
        results["operations"] = target.openapi(route, spec, tags)
        return results

    summary, desc, schema = parse_docs(target)
    responses = return_type_to_response(target)
    for method in route_to_methods(route, schema):
        results["operations"][method] = {
            "summary": summary,
            "description": desc,
            "responses": responses,
        }

    results["operations"] = merge_dicts(results["operations"], schema)
    return results


def parse_docs(cb: Callable) -> tuple[str, str, dict]:
    """Parse docs from the given callback."""
    if yaml_utils is None:
        return "", "", {}

    docs = cb.__doc__ or ""
    schema = yaml_utils.load_yaml_from_docstring(docs)
    docs = docs.split("---")[0]
    docs = utils.dedent(utils.trim_docstring(docs))
    summary, _, description = docs.partition("\n\n")
    return summary, description.strip(), schema


def merge_dicts(source: dict, merge: dict) -> dict:
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


def route_to_methods(route: Route, schema: dict | None = None) -> list[str]:
    """Get sorted methods from the route."""
    methods = [m for m in HTTP_METHODS if m in (route.methods or [])]
    if methods:
        return [m.lower() for m in methods]

    # The route accepts any method; prefer the ones declared in the docstring.
    if schema:
        methods = [m for m in HTTP_METHODS if m.lower() in schema]
        if methods:
            return [m.lower() for m in methods]

    return list(DEFAULT_METHODS)


def return_type_to_response(fn: Callable) -> dict:
    """Generate reponses specs based on the given function's return type."""
    responses: dict[int, dict] = {}
    ann = inspect.get_annotations(fn, eval_str=False)
    return_type = ann.get("return")
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
    def openapi(cls, route: Route, spec: APISpec, tags: dict) -> dict:  # noqa: C901
        """Get openapi specs for the endpoint."""
        meta = cls.meta
        if getattr(meta, meta.base_property, None) is None:
            return {}

        operations: dict = {}
        summary, _, schema = parse_docs(cls)
        if cls not in tags:
            tags[cls] = meta.name
            spec.tag({"name": meta.name, "description": summary})
            schema_name = f"{meta.name.title()}Schema"
            if schema_name not in spec.components.schemas:
                spec.components.schema(schema_name, schema=meta.Schema)

        schema_ref = {"$ref": f"#/components/schemas/{meta.name.title()}Schema"}
        for method in route_to_methods(route):
            operations[method] = {"tags": [tags[cls]]}
            is_resource_route = isinstance(route, DynamicRoute) and route.params.get("id")

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
                                "minimum": meta.limit_min,
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

            elif method == "delete" and not is_resource_route:
                operations[method]["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                }

            elif method in {"post", "put"}:
                body_schema = schema_ref
                if method == "post":
                    body_schema = {"oneOf": [schema_ref, {"type": "array", "items": schema_ref}]}
                operations[method]["requestBody"] = {
                    "required": True,
                    "content": {"application/json": {"schema": body_schema}},
                }

            if meth:
                (operations[method]["summary"], operations[method]["description"], mschema) = (
                    parse_docs(meth)
                )
                responses = return_type_to_response(meth)
                if not responses:
                    if method == "delete":
                        responses = {200: {"description": "Request is successful"}}
                    else:
                        body_schema = (
                            {"type": "array", "items": schema_ref}
                            if method == "get" and not is_resource_route
                            else schema_ref
                        )
                        responses = {
                            200: {
                                "description": "Request is successful",
                                "content": {"application/json": {"schema": body_schema}},
                            },
                        }

                operations[method]["responses"] = responses
                operations[method] = merge_dicts(operations[method], mschema)

        return merge_dicts(operations, schema)
