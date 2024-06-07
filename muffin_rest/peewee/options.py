from typing import Type

import peewee as pw
from marshmallow_peewee import ModelSchema
from peewee_aio import Manager

from muffin_rest.options import RESTOptions

from .filters import PWFilters
from .sorting import PWSorting


class PWRESTOptions(RESTOptions):
    """Support Peewee."""

    # Base filters class
    filters_cls: Type[PWFilters] = PWFilters

    # Base sorting class
    sorting_cls: Type[PWSorting] = PWSorting

    Schema: Type[ModelSchema]

    # Schema auto generation params
    schema_base: Type[ModelSchema] = ModelSchema

    base_property: str = "model"

    model: Type[pw.Model]
    model_pk: pw.Field

    manager: Manager

    # Recursive delete
    delete_recursive = False

    def setup(self, cls):
        """Prepare meta options."""
        meta = self.model._meta  # type: ignore[]
        self.name = self.name or meta.table_name.lower()
        self.model_pk = getattr(self, "model_pk", None) or meta.primary_key
        manager = getattr(self, "manager", getattr(self.model, "_manager", None))
        if manager is None:
            raise RuntimeError("Peewee-AIO ORM Manager is not available")

        self.manager = manager

        super().setup(cls)

    def setup_schema_meta(self, _):
        """Prepare a schema."""
        return type(
            "Meta",
            (object,),
            dict(
                {"unknown": self.schema_unknown, "model": self.model},
                **self.schema_meta,
            ),
        )
