PACKAGE = muffin_rest
VIRTUAL_ENV ?= .venv

# =============
#  Development
# =============

$(VIRTUAL_ENV): poetry.lock
	@poetry install --with tests,dev,example --extras yaml
	@poetry self add poetry-bumpversion
	@poetry run pre-commit install --hook-type pre-push
	@touch $(VIRTUAL_ENV)

.PHONY: t test
# target: test - Runs tests
t test: $(VIRTUAL_ENV)
	docker start mongo
	@echo 'Run tests...'
	@poetry run pytest tests
	docker stop mongo

.PHONY: mypy
# target: mypy - Check typing
mypy: $(VIRTUAL_ENV)
	@echo 'Checking typing...'
	@poetry run mypy

.PHONY: lint
# target: lint - Check code
lint: $(VIRTUAL_ENV)
	@poetry run mypy
	@poetry run ruff $(PACKAGE)

.PHONY: example-peewee
# target: example-peewee - Run example
example-peewee: $(VIRTUAL_ENV)
	@echo 'Run example...'
	@poetry run uvicorn examples.peewee_orm:app --reload --port=5000

.PHONY: example-sqlalchemy
# target: example-sqlalchemy - Run example
example-sqlalchemy: $(VIRTUAL_ENV)
	@echo 'Run example...'
	@poetry run uvicorn examples.sqlalchemy_core:app --reload --port=5000

# ==============
#  Bump version
# ==============

.PHONY: release
VPART?=minor
# target: release - Bump version
release: $(VIRTUAL_ENV)
	git checkout develop
	git pull
	git checkout master
	git merge develop
	git pull
	@poetry version $(VPART)
	git commit -am "Bump version: `poetry version -s`"
	git tag `poetry version -s`
	git checkout develop
	git merge master
	git push --tags origin develop master

.PHONY: minor
minor: release

.PHONY: patch
patch:
	make release VPART=patch

.PHONY: major
major:
	make release VPART=major

version v:
	@poetry version -s
