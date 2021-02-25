import marshmallow as ma
from marshmallow_peewee import ModelSchema

from .models import Pet, Category


class CategorySchema(ModelSchema):

    class Meta:
        model = Category


class PetSchema(ModelSchema):

    category = ma.fields.Nested(CategorySchema)

    class Meta:
        model = Pet
        dump_only = 'created',

    @ma.post_load
    def post_load(self, pet: Pet, **kwargs) -> Pet:
        """Create/load categories."""
        pet.category, _ = Category.get_or_create(name=pet.category.name)
        return pet
