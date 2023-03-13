PACKAGE = muffin_rest
VIRTUAL_ENV ?= .venv

all: $(VIRTUAL_ENV)

.PHONY: clean
# target: clean - Display callable targets
clean:
	rm -rf build/ dist/ docs/_build *.egg-info
	find $(CURDIR) -name "*.py[co]" -delete
	find $(CURDIR) -name "*.orig" -delete
	find $(CURDIR)/$(MODULE) -name "__pycache__" | xargs rm -rf

# =============
#  Development
# =============

$(VIRTUAL_ENV): pyproject.toml
	@poetry install --with tests,dev,example,yaml
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
VERSION?=minor
# target: release - Bump version
release: $(VIRTUAL_ENV)
	@$(eval VFROM := $(shell poetry version -s))
	@poetry version $(VERSION)
	@git commit -am "Bump version from $(VFROM) → `poetry version -s`"
	@git tag `poetry version -s`
	@git checkout master
	@git merge develop
	@git checkout develop
	@git push origin develop master
	@git push --tags

.PHONY: minor
minor: release

.PHONY: patch
patch:
	make release VERSION=patch

.PHONY: major
major:
	make release VERSION=major
