Muffin-REST
###########

.. _description:

**Muffin-REST** -- provides enhanced support for writing REST APIs with Muffin_.


.. _badges:

.. image:: https://github.com/klen/muffin-rest/workflows/tests/badge.svg
    :target: https://github.com/klen/muffin-rest/actions
    :alt: Tests Status

.. image:: https://img.shields.io/pypi/v/muffin-rest
    :target: https://pypi.org/project/muffin-rest/
    :alt: PYPI Version

.. image:: https://img.shields.io/pypi/pyversions/muffin-rest
    :target: https://pypi.org/project/muffin-rest/
    :alt: Python Versions

----------

.. _features:

Features
--------

- API class to simplify the creation of REST APIs;
- Automatic filtering and sorting for resources;
- Support for `Peewee ORM`_, Mongo_, `SQLAlchemy Core`_;
- Auto documentation with Swagger_;

.. _contents:

.. contents::

.. _requirements:

Requirements
=============

- python >= 3.7

.. note:: Trio is only supported with Peewee ORM

.. _installation:

Installation
=============

**Muffin-REST** should be installed using pip: ::

    pip install muffin-rest

With `SQLAlchemy Core`_ support: ::

    pip install muffin-rest[sqlalchemy]

With `Peewee ORM`_ support: ::

    pip install muffin-rest[peewee]

With YAML support for autodocumentation: ::

    pip install muffin-rest[yaml]

.. _usage:

Usage
=====

Create an API:

.. code-block:: python

   from muffin_rest import API

   api = API()

Create endpoints and connect them to the API (example for sqlalchemy):

.. code-block:: python

   from muffin_rest.sqlalchemy import SAEndpoint
   from project.api import api

   @api.route
   class MyEndpoint(SAEndpoint):

        class Meta:
            table = MyTable
            database = db

Connect it to your Muffin_ application:

.. code-block:: python

   from project.api import api

   api.setup(app, prefix='/api/v1')


.. _bugtracker:

Bug tracker
===========

If you have any suggestions, bug reports or
annoyances please report them to the issue tracker
at https://github.com/klen/muffin-rest/issues

.. _contributing:

Contributing
============

Development of Muffin-REST happens at: https://github.com/klen/muffin-rest


Contributors
=============

* klen_ (Kirill Klenov)

.. _license:

License
========

Licensed under a `MIT license`_.

.. _links:

.. _klen: https://github.com/klen
.. _Muffin: https://github.com/klen/muffin
.. _Swagger: https://swagger.io/tools/swagger-ui/
.. _Mongo: https://www.mongodb.com/
.. _Peewee ORM: http://docs.peewee-orm.com/en/latest/
.. _SqlAlchemy Core: https://docs.sqlalchemy.org/en/14/core/

.. _MIT license: http://opensource.org/licenses/MIT
