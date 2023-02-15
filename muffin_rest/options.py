"""REST Options."""

from typing import Dict, Type

import marshmallow as ma

from .filters import Filters
from .sorting import Sorting


class RESTOptions:
    """Handler Options."""

    name: str = ""
    name_id: str = "id"

    # limit: Paginate results (set to None for disable pagination)
    limit: int = 0
    limit_max: int = 0

    # Base class for filters
    filters: Filters
    filters_cls: Type[Filters] = Filters

    # Base class for sorting
    sorting: Sorting
    sorting_cls: Type[Sorting] = Sorting

    # Auto generation for schemas
    Schema: Type[ma.Schema]
    schema_base: Type[ma.Schema] = ma.Schema
    schema_fields: Dict = {}
    schema_meta: Dict = {}
    schema_unknown: str = ma.EXCLUDE

    base_property: str = "name"

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
