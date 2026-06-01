"""Shared fixtures for all test modules."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from os.path import join
from typing import TYPE_CHECKING

import pytest

from repo_lib import Repository

if TYPE_CHECKING:
    from collections.abc import Generator

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_repo_script() -> str:
    # Under pybuild the build tree does not contain the repo launcher, so
    # walk up from the test directory to the source checkout that holds
    # both the script and the repo_lib package.
    directory = PROJECT_DIR
    while True:
        candidate = join(directory, "repo")
        if os.path.isfile(candidate) and os.path.isdir(
            join(directory, "repo_lib"),
        ):
            return candidate
        parent = os.path.dirname(directory)
        if parent == directory:
            return join(PROJECT_DIR, "repo")
        directory = parent


REPO_SCRIPT = _find_repo_script()


def run_repo(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/usr/bin/python3", REPO_SCRIPT, *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=PROJECT_DIR,
        env={**os.environ, "PYTHONPATH": PROJECT_DIR},
    )


@pytest.fixture
def tempdir() -> Generator[str]:
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def repo_root(tempdir: str) -> str:
    os.makedirs(join(tempdir, "pool", "main"))
    return tempdir


@pytest.fixture
def indexed_root(repo_root: str) -> str:
    Repository(
        repo_root, "trixie", "pool", "1.0", "testorigin",
    ).index("main", "amd64")
    return repo_root
