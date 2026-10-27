"""Support openapi."""

from __future__ import annotations

from typing import TYPE_CHECKING

from muffin_rest.openapi import OpenAPIMixin

if TYPE_CHECKING:
    from .options import PWRESTOptions


class PeeweeOpenAPIMixin(OpenAPIMixin):
    """Render openapi."""

    meta: PWRESTOptions  # type: ignore[override]
