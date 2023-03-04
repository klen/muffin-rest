"""Support openapi."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from muffin_rest.openapi import OpenAPIMixin

if TYPE_CHECKING:
    from apispec import APISpec
    from http_router.routes import Route

    from .options import PWRESTOptions


class PeeweeOpenAPIMixin(OpenAPIMixin):
    """Render openapi."""

    meta: PWRESTOptions

    @classmethod
    def openapi(cls, route: Route, spec: APISpec, tags: Dict) -> Dict:
        """Get openapi specs for the endpoint."""
        operations = super(PeeweeOpenAPIMixin, cls).openapi(route, spec, tags)
        is_resource_route = getattr(route, "params", {}).get(cls.meta.name_id)
        if not is_resource_route and "delete" in operations:
            operations["delete"].setdefault("parameters", [])
            operations["delete"]["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        return operations
