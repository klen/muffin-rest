import enum

import sqlalchemy as sa

from . import app, db

meta = sa.MetaData()
Category = sa.Table(
    "category",
    meta,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
)


class Statuses(enum.Enum):
    available = "available"
    pending = "pending"
    sold = "sold"


Pet = sa.Table(
    "pet",
    meta,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("image", sa.String(255), nullable=False),
    sa.Column("status", sa.Enum(Statuses), nullable=False),
    sa.Column("category_id", sa.ForeignKey("category.id"), nullable=False),
)


# don't do on production, this is only for the example
@app.on_startup
async def create_schema():
    meta.create_all(sa.create_engine(db.cfg.URL))
