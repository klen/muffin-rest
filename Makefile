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

outdated:
	@echo "Checking for outdated dependencies..."
	@uv tree --depth 1 --outdated | grep 'latest' || echo "All dependencies are up to date."

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

RELEASE	?= minor
MANAGER	?= uv

.PHONY: release
# target: release - Bump version
release:
	@echo "Starting release process (bumping $(RELEASE) version)..."
	@git checkout main
	@git pull
	@git checkout develop
	@git pull
	@echo "Bumping version and creating release commit and tag..."
	@uvx bump-my-version bump $(RELEASE)
	@echo "Version bumped to `$(MANAGER) version --short`."
	@$(MANAGER) lock
	@echo "Committing version bump and creating tag..."
	@VERSION=`$(MANAGER) version --short`; \
		{ \
			printf 'build(release): %s\n\n' "$$VERSION"; \
			printf 'Changes:\n\n'; \
			git log --oneline --pretty=format:'%s [%an]' main..develop | grep -Evi 'github|^Merge' || true; \
		} | git commit -a -F -
	@echo "Merging changes between branches..."
	@git checkout main
	@git merge --ff-only develop
	@VERSION=`$(MANAGER) version --short`; \
		git push origin main; \
		git tag -a "$$VERSION" -m "$$VERSION"; \
		git push origin "$$VERSION"
	@git checkout develop
	@git merge --ff-only main
	@git push origin develop
	@echo "Release process complete for `$(MANAGER) version --short`"

.PHONY: minor
minor: release

.PHONY: patch
patch:
	make release RELEASE=patch

.PHONY: major
major:
	make release RELEASE=major

version v:
	uv version --short
