# Agent Notes

## Fast Setup

- Use `uv` for everything; this repo is configured around `uv.lock` and `uv_build`.
- First-time local setup: `make` (runs `uv sync` and installs pre-commit hooks).
- CI-equivalent dependency sync: `uv sync --locked --all-extras --dev`.

## Verify Changes

- Preferred local order matches CI/Makefile:
  `uv run pyrefly check` -> `uv run ruff check` -> `uv run pytest`.
- `make lint` already runs typecheck + lint; `make test` runs full tests with Mongo start/stop.
- Full suite needs a local Docker container named `mongo` (`docker start mongo`),
  otherwise Mongo tests and pre-push hooks fail.
- Pytest defaults from `pyproject.toml` are `-xsv tests` (stop on first failure, verbose,
  only `tests/`).
- Focused run example: `uv run pytest tests/test_peewee.py::test_base`.

## Hooks And Commit Constraints

- Pre-commit includes: `ruff format`, `ruff check`, `pyrefly check`, and `uv-lock --check`.
- If dependency metadata changes, run `uv lock` before committing or hook will fail.
- Commit messages are validated against conventional commit types in `.git-commits.yaml`.
- Pre-push hook runs full `uv run pytest`
  and wraps it with `docker start mongo` / `docker stop mongo`.

## Codebase Map

- Core wiring:
  - `muffin_rest/api.py` -> `API` router/docs setup.
  - `muffin_rest/handler.py` -> generic REST flow (auth, filters, sorting, pagination,
    CRUD methods).
  - Backend handlers:
    - Peewee: `muffin_rest/peewee/handler.py` (`PWRESTHandler`)
    - SQLAlchemy Core: `muffin_rest/sqlalchemy/__init__.py` (`SARESTHandler`)
    - Mongo: `muffin_rest/mongo/__init__.py` (`MongoRESTHandler`)
- `@api.route` on a `RESTHandler` subclass auto-binds list/detail routes
  when no explicit path is given.

## Repo-Specific Gotchas

- Keep naming consistent with code/tests: public handler classes are `PWRESTHandler`,
  `SARESTHandler`, `MongoRESTHandler` (not `*Endpoint`).
- API docs endpoints created by `API.setup()` are `/swagger`, `/redoc`,
  and `/openapi.json` under API prefix (for example `/api/openapi.json`).
- Async test behavior is intentional: base tests use an autouse asyncio/trio/curio matrix,
  while backend-specific suites pin to asyncio via local `aiolib` fixtures.
