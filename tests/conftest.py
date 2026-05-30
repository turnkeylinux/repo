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
REPO_SCRIPT = join(PROJECT_DIR, "repo")


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
