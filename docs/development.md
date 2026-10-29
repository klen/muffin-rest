# Development

The project uses `uv` for dependencies, `ruff` for formatting and linting,
`pyrefly` for types, and `pytest` for tests.

## Setup

```bash
make
```

`make` runs `uv sync` and installs the pre-commit hooks. The equivalent manual
steps are:

```bash
uv sync --locked --all-extras --dev
uv run pre-commit install
```

Python 3.11 or newer is required. CI runs 3.11 through 3.15.

## Checks

Run the same order as CI:

```bash
uv run pyrefly check
uv run ruff check
uv run pytest
```

`make lint` runs the first two. `make test` starts the `mongo` Docker container,
runs the full suite, and stops the container.

Pytest defaults come from `pyproject.toml`: `-xsv tests`, so the suite stops on
the first failure. A focused run:

```bash
uv run pytest tests/test_peewee.py::test_base
```

The base tests run under asyncio, trio, and curio. Backend tests pin asyncio
because the database drivers do. The Mongo tests need a local Docker container
named `mongo`:

```bash
docker start mongo
uv run pytest
```

Pre-commit runs formatting, linting, typing, and `uv lock --check` before a
commit. The pre-push hook runs the full test suite with the Mongo container.
If dependency metadata changes, run `uv lock` before committing.

Commit messages must follow the conventional types in `.git-commits.yaml`:
`build`, `chore`, `docs`, `feat`, `fix`, `merge`, `ops`, `perf`, `refactor`,
`style`, `test`.

## Examples

The examples run against SQLite and are the quickest way to see a complete
application:

```bash
uv run uvicorn examples.peewee_orm:app --reload --port=5000
uv run uvicorn examples.sqlalchemy_core:app --reload --port=5000
```

Both redirect `/` to `/api/swagger`. The Peewee example uses `muffin_peewee`;
the SQLAlchemy example uses `muffin_databases`.

## Layout

The code is organized by responsibility, not by backend:

- `muffin_rest/api.py`: API router, docs routes, authorization callback
- `muffin_rest/handler.py`: request lifecycle, CRUD, query pipeline
- `muffin_rest/openapi.py`: spec generation
- `muffin_rest/filters.py`, `sorting.py`: generic query handling
- `muffin_rest/options.py`: `Meta` options and generated schemas
- `muffin_rest/peewee/`, `sqlalchemy/`, `mongo/`: backend implementations

A backend supplies `prepare_collection`, `prepare_resource`, `paginate`, `save`,
and `remove`, plus its own filter and sorter classes. If you add a backend,
start from `RESTHandler` and implement those five methods.

## Documentation

The guides live in `docs/` as Markdown and are built with MkDocs Material:

```bash
make docs          # build site/ with --strict
make docs-serve    # preview at http://127.0.0.1:8000
```

The `docs` dependency group is separate from `dev`, so the database drivers and
test tools are not installed just to build the site. The README is the entry
point and links to the guides. When you add a page, add it to the `nav` in
`mkdocs.yml`, and link it from `docs/index.md` and the README table.

`.github/workflows/docs.yml` builds the site and publishes it to GitHub Pages
on pushes to `develop` (the default branch). The repository must have Pages
enabled with the source set to GitHub Actions.

## Release

Releases are cut from `develop` into `main`:

```bash
make release          # minor by default
make patch
make major
```

The target bumps the version with `bump-my-version`, updates `uv.lock`, creates a
release commit and tag, pushes `main`, and merges back into `develop`. Publishing
to PyPI happens in the release workflow after the tests pass on `main`.
