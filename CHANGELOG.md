# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `MultiFilter` for filters that parse a nested object and combine child filters; `filters` accepts the same entries as `Meta.filters`.
- Python 3.15 support.
- `limit_min` pagination option (default `1`). Set it to `0` to allow `limit=0` to return all rows.
- Documentation guides in `docs/`: tutorial, handler lifecycle, backends, custom backend, querying, schemas, OpenAPI, errors, cookbook, API reference, and development.
- MkDocs Material build (`make docs`, `make docs-serve`) and a GitHub Pages workflow.

### Fixed

- Custom handler routes use the decorated method's docstring and YAML in the OpenAPI spec.
- Compatibility with Muffin 3 and http-router 10: `RESTBase.__route__` accepts `methods`/`hosts` and 3-tuple method routes.
- Explicit `SAFilter`/`PWFilter` instances with string fields are resolved to table columns; expression fields (e.g. `JSONPath`) are left as-is.
- Mongo list endpoints work without pagination or sorting (`MongoChain.to_list`).
- Mongo aggregate pagination no longer calls `list()` on an async cursor and no longer mutates the shared `Meta.aggregate` pipeline.
- Default REST endpoints now accept only `get/post/put/delete`, so PATCH, HEAD and OPTIONS return 405 instead of 500.
- Mongo `$starts` and `$ends` escape user values before building the regex.
- `MemoryRateLimiter` drops expired keys instead of growing without bound.
- Sorting applies fields in the order given in the `sort` parameter.
- `schema_only` and `schema_exclude` accept comma-separated field names.
- Filter `$in` and `$or/$and/$not/$nor` operators are corrected; SQLAlchemy and Peewee gained SQL logic operators.
- Pagination clamps a negative `offset` to `0` and the `limit` to `[limit_min, limit_max]`.

### Changed

- Dependency bumps: `marshmallow>=4,<5` (marshmallow 3 is no longer supported), `marshmallow-peewee` 6, `muffin` 3.2, `apispec>=6.8.1` (first release with marshmallow 4 support).
- `schema_meta = {"additional": ...}` raises `ValueError`: marshmallow 4 dropped the option, and it would otherwise be ignored silently. Declare the fields in `schema_fields`.
- `methods` is validated when the handler class is created (Muffin 3.2): a method declared in `methods` without an implementation raises `TypeError` on import instead of returning 500 at runtime. Declare only the methods you implement.
- `Filters.apply` calls every filter; each filter checks whether its own keys are present in `where`. This prepares multi-field filters.
- SQLAlchemy delete and batch operation tests are enabled again.

### Removed

- `Filter.get_simple_value`.

## [13.5.0] - 2026-04-10

### Added

- Peewee composite primary key support for resource lookup by route `id`.
- `CompositePKField` in `muffin_rest.peewee.schemas` for dumping composite keys as a string id.
- Peewee tests for composite key API behavior and composite key schema serialization.

### Changed

- Peewee single-resource lookup now converts primary key values via model field python converters.
- Composite key helpers were added to parse and render ids with a stable separator.

## [4.0.0] - 2021-11-01

### Changed

- Filters and sorting are async now

## [3.5.1] - 2021-10-21

### Changed

- Minimal version for `marshmallow-peewee` now is `3.2`

## [3.5.0] - 2021-10-20

### Added

- Support for python 3.10

## [3.4.4] - 2021-09-16

### Added

### Changed

### Removed

[Unreleased]: https://github.com/klen/muffin-rest/compare/13.4.0...HEAD
[3.5.1]: https://github.com/klen/muffin-rest/compare/3.5.1...4.0.0
[3.5.1]: https://github.com/klen/muffin-rest/compare/3.5.0...3.5.1
[3.5.0]: https://github.com/klen/muffin-rest/compare/3.4.4...3.5.0
[3.4.4]: https://github.com/klen/muffin-rest/compare/0.1.0...3.4.4
[0.1.0]: https://github.com/klen/aio-apiclient/releases/tag/0.1.0
