Muffin‑REST
===========

**Muffin‑REST** simplifies building RESTful APIs with Muffin_ by offering:

- Declarative `API` class with resource registration
- Built-in filtering, sorting, pagination, and search
- Support for:
  - `Peewee ORM`_ via `PeeweeEndpoint`
  - `SQLAlchemy Core`_ via `SAEndpoint`
  - `MongoDB`_ via `MongoEndpoint`
- Swagger/OpenAPI autodocumentation
- Works with asyncio, Trio, and Curio

.. image:: https://github.com/klen/muffin-rest/workflows/tests/badge.svg
   :target: https://github.com/klen/muffin-rest/actions
   :alt: Tests Status

.. image:: https://img.shields.io/pypi/v/muffin-rest
   :target: https://pypi.org/project/muffin-rest/
   :alt: PyPI Version

.. image:: https://img.shields.io/pypi/pyversions/muffin-rest
   :target: https://pypi.org/project/muffin-rest/
   :alt: Python Versions

.. contents::

Requirements
============

- Python >= 3.10
- Trio requires Peewee backend
- Latest release: v11.0.1 (Jun 13, 2025)

Installation
============

Install core package:

    pip install muffin-rest

Add optional backend support:

- SQLAlchemy Core: ``pip install muffin-rest[sqlalchemy]``
- Peewee ORM: ``pip install muffin-rest[peewee]``
- YAML support for Swagger: ``pip install muffin-rest[yaml]``

Quickstart (Peewee example)
===========================

.. code-block:: python

    from muffin import Application
    from muffin_rest import API
    from muffin_rest.peewee import PeeweeEndpoint
    from models import User  # your Peewee model

    app = Application("myapp")
    api = API(title="User Service", version="1.0")

    @api.route
    class UsersEndpoint(PeeweeEndpoint):
        class Meta:
            model = User
            lookup_field = "id"
            filters = ["name", "email"]
            ordering = ["-created_at"]

    api.setup(app, prefix="/api", swagger=True)

Endpoints available:

- `GET    /api/users/` — list with pagination, search, filtering
- `POST   /api/users/` — create
- `GET    /api/users/{id}/` — retrieve
- `PUT    /api/users/{id}/` — replace
- `PATCH  /api/users/{id}/` — update
- `DELETE /api/users/{id}/` — remove
- Docs: `/api/docs/`, OpenAPI spec: `/api/openapi.json`

Usage with SQLAlchemy
=====================

.. code-block:: python

    from muffin_rest import API
    from muffin_rest.sqlalchemy import SAEndpoint
    from models import my_table, db_engine

    api = API()
    @api.route
    class MySAEndpoint(SAEndpoint):
        class Meta:
            table = my_table
            database = db_engine

    api.setup(app)

Usage with MongoDB
==================

.. code-block:: python

    from muffin_rest import API
    from muffin_rest.mongo import MongoEndpoint
    from models import mongo_collection

    api = API()
    @api.route
    class MyMongoEndpoint(MongoEndpoint):
        class Meta:
            collection = mongo_collection

    api.setup(app)

Advanced Configuration
======================

Customize Swagger and routes via constructor:

.. code-block:: python

    api = API(
        title="Service API",
        version="2.1",
        swagger_ui=True,
        openapi_path="/api/openapi.json",
        docs_path="/api/docs/"
    )

Contributing & Examples
=======================

- See `examples/` for live application demos
- Tests in `tests/` focus on filtering, pagination, status codes
- Check `CHANGELOG.md` for latest changes

Bug Tracker
===========

Report bugs or request features:
https://github.com/klen/muffin-rest/issues

Contributing
============

Repo: https://github.com/klen/muffin-rest
Pull requests, example additions, docs improvements welcome!

Contributors
============

- klen_ (Kirill Klenov)

License
=======

Licensed under the `MIT license`_.

.. _Muffin: https://github.com/klen/muffin
.. _Peewee ORM: http://docs.peewee-orm.com/en/latest/
.. _SQLAlchemy Core: https://docs.sqlalchemy.org/en/14/core/
.. _MongoDB: https://www.mongodb.com/
.. _Swagger/OpenAPI: https://swagger.io/
.. _MIT license: http://opensource.org/licenses/MIT
