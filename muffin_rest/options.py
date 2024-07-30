"""REST Options."""

from typing import Any, Dict, Type

import marshmallow as ma

from muffin_rest.limits import MemoryRateLimiter, RateLimiter

from .filters import Filters
from .sorting import Sorting


class RESTOptions:
    """Handler Options."""

    name: str = ""
    name_id: str = "id"
    base_property: str = "name"

    # Pagination
    # ----------

    # limit: Paginate results (set to None for disable pagination)
    limit: int = 0

    # limit_max: Max limit for pagination
    limit_max: int = 0

    # limit_total: Return total count of results
    limit_total: bool = True

    # Filters
    # -------

    # Base class for filters
    filters: Filters
    filters_cls: Type[Filters] = Filters

    # Sorting
    # -------

    # Base class for sorting
    sorting: Sorting
    sorting_cls: Type[Sorting] = Sorting

    # Serialization/Deserialization
    # -----------------------------

    # Auto generation for schemas
    Schema: Type[ma.Schema]
    schema_base: Type[ma.Schema] = ma.Schema
    schema_fields: Dict = {}
    schema_meta: Dict = {}
    schema_unknown: str = ma.EXCLUDE

    # Rate Limiting
    # -------------

    rate_limit: int = 0
    rate_limit_period: int = 60
    rate_limit_cls: Type[RateLimiter] = MemoryRateLimiter
    rate_limit_cls_opts: Dict[str, Any] = {}

    def __init__(self, cls):
        """Inherit meta options."""
        for base in reversed(cls.mro()):
            if hasattr(base, "Meta"):
                for k, v in base.Meta.__dict__.items():
                    if not k.startswith("_"):
                        setattr(self, k, v)

        if getattr(self, self.base_property, None) is not None:
            self.setup(cls)

    def setup(self, cls):
        """Setup the options."""
        self.name = self.name or cls.__name__.lower()
        if not self.Schema:
            name = self.name or "Unknown"
            self.Schema = type(
                name.title() + "Schema",
                (self.schema_base,),
                dict(self.schema_fields, Meta=self.setup_schema_meta(cls)),
            )

        if not self.limit_max:
            self.limit_max = self.limit

        if self.rate_limit:
            self.rate_limiter = self.rate_limit_cls(
                self.rate_limit, self.rate_limit_period, **self.rate_limit_cls_opts
            )

    def setup_schema_meta(self, _):
        """Generate meta for schemas."""
        return type(
            "Meta",
            (object,),
            dict({"unknown": self.schema_unknown}, **self.schema_meta),
        )

    def __repr__(self):
        """Represent self as a string."""
        return f"<Options {self.name}>"
