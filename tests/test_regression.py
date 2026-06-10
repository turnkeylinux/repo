"""Regression tests for repo index and repo release."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from os.path import exists, join
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from repo_lib import RepoError, Repository

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


def build_deb(dest_dir: str, name: str, version: str, arch: str) -> str:
    # Build a minimal but valid .deb with dpkg-deb so apt-ftparchive has
    # real package metadata to index.
    build_dir = join(dest_dir, f"{name}-build")
    debian_dir = join(build_dir, "DEBIAN")
    os.makedirs(debian_dir)
    with open(join(debian_dir, "control"), "w") as fob:
        fob.writelines(
            [
                f"Package: {name}\n",
                f"Version: {version}\n",
                f"Architecture: {arch}\n",
                "Maintainer: Test <test@example.com>\n",
                "Description: test package\n",
            ],
        )
    deb_path = join(dest_dir, f"{name}_{version}_{arch}.deb")
    subprocess.run(
        ["/usr/bin/dpkg-deb", "--build", build_dir, deb_path],
        capture_output=True,
        text=True,
        check=True,
    )
    return deb_path


def gen_signing_key(gnupghome: str, uid: str) -> None:
    # Generate a throwaway, passphraseless signing key in an isolated
    # GNUPGHOME so the release signing path can be exercised without
    # touching any real keyring.
    os.makedirs(gnupghome, mode=0o700)
    subprocess.run(
        [
            "/usr/bin/gpg",
            "--homedir",
            gnupghome,
            "--batch",
            "--pinentry-mode",
            "loopback",
            "--passphrase",
            "",
            "--quick-generate-key",
            uid,
            "default",
            "default",
            "0",
        ],
        capture_output=True,
        text=True,
        check=True,
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
def populated_root(repo_root: str) -> str:
    build_deb(join(repo_root, "pool", "main"), "testpkg", "1.2.3", "amd64")
    return repo_root


@pytest.fixture
def indexed_root(repo_root: str) -> str:
    Repository(
        repo_root, "trixie", "pool", "1.0", "testorigin",
    ).index("main", "amd64")
    return repo_root


class TestIndex:
    def test_creates_packages_and_compressed_variants(
        self, repo_root: str,
    ) -> None:
        Repository(repo_root, "trixie", "pool", "1.0", "origin").index(
            "main", "amd64",
        )
        binary_dir = join(
            repo_root, "dists", "trixie", "main", "binary-amd64",
        )
        for name in (
            "Packages", "Packages.gz", "Packages.bz2", "Packages.xz",
        ):
            assert exists(join(binary_dir, name)), f"missing {name}"

    def test_indexes_real_package_metadata(
        self, populated_root: str,
    ) -> None:
        Repository(populated_root, "trixie", "pool", "1.0", "origin").index(
            "main", "amd64",
        )
        packages_path = join(
            populated_root,
            "dists",
            "trixie",
            "main",
            "binary-amd64",
            "Packages",
        )
        with open(packages_path) as fob:
            content = fob.read()
        assert "Package: testpkg\n" in content
        assert "Version: 1.2.3\n" in content
        assert "Architecture: amd64\n" in content
        assert "Filename: pool/main/" in content

    def test_component_release_file_content(self, repo_root: str) -> None:
        Repository(repo_root, "trixie", "pool", "1.0", "myorg").index(
            "main", "amd64",
        )
        release_path = join(
            repo_root,
            "dists",
            "trixie",
            "main",
            "binary-amd64",
            "Release",
        )
        with open(release_path) as fob:
            content = fob.read()
        assert "Archive: trixie\n" in content
        assert "Origin: myorg\n" in content
        assert "Label: myorg\n" in content
        assert "Version: 1.0\n" in content
        assert "Component: main\n" in content
        assert "Architecture: amd64\n" in content

    def test_missing_component_raises(self, repo_root: str) -> None:
        with pytest.raises(RepoError, match="does not exist"):
            Repository(
                repo_root, "trixie", "pool", "1.0", "origin",
            ).index("nonexistent", "amd64")

    def test_missing_repo_path_raises(self, tempdir: str) -> None:
        with pytest.raises(RepoError, match="does not exist"):
            Repository(
                join(tempdir, "no-such-dir"),
                "trixie",
                "pool",
                "1.0",
                "origin",
            )

    def test_cli_index_succeeds(self, repo_root: str) -> None:
        result = run_repo("index", repo_root, "trixie", "main", "amd64")
        assert result.returncode == 0

    def test_cli_no_subcommand_exits_nonzero(self) -> None:
        result = run_repo()
        assert result.returncode != 0

    def test_cli_index_missing_args_exits_nonzero(self) -> None:
        result = run_repo("index")
        assert result.returncode != 0

    def test_cli_unsupported_arch_exits_nonzero(
        self, repo_root: str,
    ) -> None:
        result = run_repo("index", repo_root, "trixie", "main", "sparc")
        assert result.returncode != 0

    def test_cli_nonexistent_repo_exits_nonzero(
        self, tempdir: str,
    ) -> None:
        result = run_repo(
            "index",
            join(tempdir, "no-such-dir"),
            "trixie",
            "main",
            "amd64",
        )
        assert result.returncode != 0


class TestRelease:
    def test_creates_release_file(self, indexed_root: str) -> None:
        Repository(
            indexed_root, "trixie", "pool", "1.0", "origin",
        ).generate_release()
        assert exists(join(indexed_root, "dists", "trixie", "Release"))

    def test_no_gpg_files_without_key(self, indexed_root: str) -> None:
        Repository(
            indexed_root, "trixie", "pool", "1.0", "origin",
        ).generate_release()
        dist_dir = join(indexed_root, "dists", "trixie")
        assert not exists(join(dist_dir, "Release.gpg"))
        assert not exists(join(dist_dir, "InRelease"))

    def test_release_file_content(self, indexed_root: str) -> None:
        Repository(
            indexed_root, "trixie", "pool", "1.0", "myorg",
        ).generate_release()
        with open(join(indexed_root, "dists", "trixie", "Release")) as fob:
            content = fob.read()
        assert "Origin: myorg\n" in content
        assert "Label: myorg\n" in content
        assert "Suite: trixie\n" in content
        assert "Codename: trixie\n" in content
        assert "Version: 1.0\n" in content
        assert "Architectures: amd64\n" in content
        assert "Components: main\n" in content
        assert "Description: myorg trixie 1.0 Released" in content
        assert "SHA256:" in content

    def test_stale_release_files_are_removed(
        self, indexed_root: str,
    ) -> None:
        dist_dir = join(indexed_root, "dists", "trixie")
        for name in ("Release.gpg", "InRelease"):
            with open(join(dist_dir, name), "w") as fob:
                fob.write("stale")
        Repository(
            indexed_root, "trixie", "pool", "1.0", "origin",
        ).generate_release()
        assert not exists(join(dist_dir, "Release.gpg"))
        assert not exists(join(dist_dir, "InRelease"))

    def test_release_is_regenerated_not_stale(
        self, indexed_root: str,
    ) -> None:
        dist_dir = join(indexed_root, "dists", "trixie")
        with open(join(dist_dir, "Release"), "w") as fob:
            fob.write("stale")
        Repository(
            indexed_root, "trixie", "pool", "1.0", "origin",
        ).generate_release()
        with open(join(dist_dir, "Release")) as fob:
            content = fob.read()
        assert content != "stale"
        assert "Origin:" in content

    def test_warns_to_stderr_without_key(
        self,
        indexed_root: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        Repository(
            indexed_root, "trixie", "pool", "1.0", "origin", quiet=False,
        ).generate_release()
        captured = capsys.readouterr()
        assert "Warning" in captured.err or "unsigned" in captured.err

    def test_quiet_suppresses_warning(
        self,
        indexed_root: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        Repository(
            indexed_root, "trixie", "pool", "1.0", "origin", quiet=True,
        ).generate_release()
        captured = capsys.readouterr()
        assert "Warning" not in captured.err

    def test_signing_creates_signed_files(
        self,
        indexed_root: str,
        tempdir: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        uid = "repo-test@example.com"
        gnupghome = join(tempdir, "gnupg")
        gen_signing_key(gnupghome, uid)
        monkeypatch.setenv("GNUPGHOME", gnupghome)
        Repository(
            indexed_root, "trixie", "pool", "1.0", "origin",
        ).generate_release(uid)
        dist_dir = join(indexed_root, "dists", "trixie")
        assert exists(join(dist_dir, "Release.gpg"))
        assert exists(join(dist_dir, "InRelease"))
        # The temporary clearsign input must be cleaned up.
        assert not exists(join(dist_dir, "InRelease.tmp"))
        with open(join(dist_dir, "InRelease")) as fob:
            assert "BEGIN PGP SIGNED MESSAGE" in fob.read()

    def test_cli_release_succeeds(self, indexed_root: str) -> None:
        result = run_repo("release", indexed_root, "trixie")
        assert result.returncode == 0

    def test_cli_release_missing_args_exits_nonzero(self) -> None:
        result = run_repo("release")
        assert result.returncode != 0

    def test_cli_release_nonexistent_repo_exits_nonzero(
        self, tempdir: str,
    ) -> None:
        result = run_repo(
            "release", join(tempdir, "no-such-dir"), "trixie",
        )
        assert result.returncode != 0
