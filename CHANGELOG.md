# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
