"""Setup the package."""


# Parse requirements
# ------------------
import pkg_resources
import pathlib


def parse_requirements(path: str) -> 'list[str]':
    with pathlib.Path(path).open() as requirements:
        return [str(req) for req in pkg_resources.parse_requirements(requirements)]


# Setup package
# -------------

from setuptools import setup


setup(
    install_requires=parse_requirements('requirements/requirements.txt'),
    extras_require={
        'tests': parse_requirements('requirements/requirements-tests.txt'),
        'yaml': ['pyyaml'],
        'build': ['bump2version', 'wheel'],
        'example': ['uvicorn', 'muffin-peewee-aio', 'marshmallow-peewee'],
        'peewee': [
            'muffin-peewee-aio >= 0.2.2',
            'marshmallow-peewee >= 3.2.0',
        ],
        'sqlalchemy': [
            'muffin-databases >= 0.3.2',
            'marshmallow-sqlalchemy',
            'sqlalchemy',
        ],
    }
)

# pylama:ignore=E402,D
