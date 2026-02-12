PACKAGE = muffin_rest
VIRTUAL_ENV ?= .venv

all: $(VIRTUAL_ENV)

.PHONY: help
# target: help - Display callable targets
help:
	@egrep "^# target:" [Mm]akefile

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

$(VIRTUAL_ENV): pyproject.toml .pre-commit-config.yaml
	@uv sync
	@uv run pre-commit install
	@touch $(VIRTUAL_ENV)

.PHONY: t test
# target: test - Runs tests
t test: $(VIRTUAL_ENV)
	docker start mongo
	@echo 'Run tests...'
	@uv run pytest tests
	docker stop mongo

.PHONY: types
# target: types - Check typing
types: $(VIRTUAL_ENV)
	@echo 'Checking typing...'
	@uv run pyrefly check

.PHONY: lint
# target: lint - Check code
lint: $(VIRTUAL_ENV)
	@make types
	@uv run ruff check

.PHONY: example-peewee example-pw example
# target: example-peewee - Run example
example-peewee example-pw example: $(VIRTUAL_ENV)
	@echo 'Run example...'
	@uv run uvicorn examples.peewee_orm:app --reload --port=5000

.PHONY: example-sqlalchemy
# target: example-sqlalchemy - Run example
example-sqlalchemy: $(VIRTUAL_ENV)
	@echo 'Run example...'
	@uv run uvicorn examples.sqlalchemy_core:app --reload --port=5000

# ==============
#  Bump version
# ==============

VERSION	?= minor
MAIN_BRANCH = master

.PHONY: release
VPART?=minor
# target: release - Bump version
release:
	git checkout master
	git pull
	git checkout develop
	git pull
	uvx bump-my-version bump $(VPART)
	uv lock
	@VERSION="$$(uv version --short)"; \
		{ \
			printf 'build(release): %s\n\n' "$$VERSION"; \
			printf 'Changes:\n\n'; \
			git log --oneline --pretty=format:'%s [%an]' $(MAIN_BRANCH)..develop | grep -Evi 'github|^Merge' || true; \
		} | git commit -a -F -; \
		git tag "$$VERSION";
	git checkout $(MAIN_BRANCH)
	git merge develop
	git checkout develop
	git merge $(MAIN_BRANCH)
	git push origin develop $(MAIN_BRANCH) --tags
	@echo "Release process complete for `uv version --short`"

.PHONY: minor
minor: release

.PHONY: patch
patch:
	make release VPART=patch

.PHONY: major
major:
	make release VPART=major

version v:
	uv version --short
