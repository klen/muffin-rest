# Muffin-REST documentation

Muffin-REST adds REST resources to [Muffin](https://github.com/klen/muffin).
A handler declares a model or table in `Meta`; the library builds list and
detail routes, query handling, validation, and an OpenAPI spec around it.

The docs are split by the question you are trying to answer.

## Start here

- [Tutorial](tutorial.md): build a working API in ten minutes.
- [Handlers and lifecycle](handlers.md): what happens on a request and where to
  plug in your own code.
- [Backends](backends.md): pick Peewee, SQLAlchemy Core, or MongoDB and see the
  differences.

## Reference

- [Querying](querying.md): `where`, `sort`, `limit`, `offset`, field selection.
- [Schemas](schemas.md): generated schemas, validation, custom fields.
- [OpenAPI](openapi.md): spec generation, docstrings, authorization.
- [Errors](errors.md): error bodies and status codes.
- [API reference](reference.md): classes, options, and hook signatures.

## Practice

- [Cookbook](cookbook.md): auth, scoping, soft delete, custom filters, file
  upload, tests.
- [Development](development.md): local setup, tests, examples, release.

## How the pieces fit

```
Application
└── API                 routing, auth, OpenAPI
    └── RESTHandler     request lifecycle, CRUD, query handling
        ├── PWRESTHandler
        ├── SARESTHandler
        └── MongoRESTHandler
```

`API` owns the router and the authorization callback. A `RESTHandler` subclass
owns one resource. Backend handlers implement the storage-specific parts:
loading a collection, loading one resource, pagination, saving, and deleting.

The core is `muffin_rest.handler.RESTBase`. Read it once; every guide refers to
its hooks.
