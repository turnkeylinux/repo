"""Tests for repo download, repo release --gen-key, and repo client-config."""
from __future__ import annotations

import os
import subprocess
import tempfile
from os.path import exists, join

import pytest

from repo_lib import RepoError, Repository
from repo_lib.client import write_client_config
from repo_lib.download import (
    copy_debs_to_pool,
    installed_packages,
    resolve_deps,
)
from repo_lib.gpg import (
    cleanup_key,
    export_public_key,
    gen_and_sign,
    gen_repo_key,
)

# conftest.py provides: tempdir, repo_root, indexed_root fixtures
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
def repo_with_asc(indexed_root: str) -> str:
    # Write a placeholder key file so client-config tests do not require a
    # full GPG key-generation cycle.
    with open(join(indexed_root, "repo.asc"), "w") as fob:
        fob.write(
            "-----BEGIN PGP PUBLIC KEY BLOCK-----\n"
            "placeholder\n"
            "-----END PGP PUBLIC KEY BLOCK-----\n"
        )
    return indexed_root


class TestDownloadLib:
    def test_resolve_deps_includes_requested_package(self) -> None:
        result = resolve_deps(["bash"])
        assert "bash" in result

    def test_resolve_deps_returns_real_packages_only(self) -> None:
        # Virtual packages appear with angle brackets in apt-cache output and
        # must be filtered out so nothing with '<' appears in the result.
        result = resolve_deps(["bash"])
        for pkg in result:
            assert "<" not in pkg, f"virtual package leaked into result: {pkg}"

    def test_resolve_deps_raises_for_unknown_package(self) -> None:
        with pytest.raises(RepoError):
            resolve_deps(["no-such-package-xyzzy-999"])

    def test_installed_packages_nonempty(self) -> None:
        result = installed_packages()
        assert len(result) > 0

    def test_installed_packages_contains_dpkg(self) -> None:
        # dpkg is always installed on Debian.
        assert "dpkg" in installed_packages()

    def test_copy_debs_to_pool_copies_files(self, tempdir: str) -> None:
        # Simulate a chroot apt cache by creating the expected directory tree.
        cache_dir = join(tempdir, "var", "cache", "apt", "archives")
        pool_dir = join(tempdir, "pool")
        os.makedirs(cache_dir)
        os.makedirs(pool_dir)
        deb_names = ("pkg1_1.0_amd64.deb", "pkg2_2.0_amd64.deb")
        for name in deb_names:
            open(join(cache_dir, name), "w").close()

        count = copy_debs_to_pool(pool_dir, chroot=tempdir)

        assert count == len(deb_names)
        assert exists(join(pool_dir, "pkg1_1.0_amd64.deb"))
        assert exists(join(pool_dir, "pkg2_2.0_amd64.deb"))

    def test_copy_debs_to_pool_skips_existing_files(
        self, tempdir: str,
    ) -> None:
        cache_dir = join(tempdir, "var", "cache", "apt", "archives")
        pool_dir = join(tempdir, "pool")
        os.makedirs(cache_dir)
        os.makedirs(pool_dir)
        deb = "pkg_1.0_amd64.deb"
        with open(join(cache_dir, deb), "w") as fob:
            fob.write("cache")
        with open(join(pool_dir, deb), "w") as fob:
            fob.write("pool-original")

        count = copy_debs_to_pool(pool_dir, chroot=tempdir)

        assert count == 0
        with open(join(pool_dir, deb)) as fob:
            assert fob.read() == "pool-original"

    def test_copy_debs_to_pool_ignores_non_debs(self, tempdir: str) -> None:
        cache_dir = join(tempdir, "var", "cache", "apt", "archives")
        pool_dir = join(tempdir, "pool")
        os.makedirs(cache_dir)
        os.makedirs(pool_dir)
        open(join(cache_dir, "lockfile"), "w").close()
        open(join(cache_dir, "partial"), "w").close()
        open(join(cache_dir, "real.deb"), "w").close()

        count = copy_debs_to_pool(pool_dir, chroot=tempdir)

        assert count == 1
        assert not exists(join(pool_dir, "lockfile"))
        assert not exists(join(pool_dir, "partial"))


class TestDownloadCli:
    def test_cli_download_missing_args_exits_nonzero(self) -> None:
        result = run_repo("download")
        assert result.returncode != 0

    def test_cli_download_missing_packages_exits_nonzero(
        self, repo_root: str,
    ) -> None:
        result = run_repo("download", repo_root, "trixie", "main", "amd64")
        assert result.returncode != 0


class TestGpgLib:
    def test_gen_repo_key_creates_homedir(self, repo_root: str) -> None:
        gnupghome, _ = gen_repo_key(repo_root)
        try:
            assert exists(gnupghome)
        finally:
            cleanup_key(gnupghome)

    def test_gen_repo_key_uid_contains_repo_name(self, repo_root: str) -> None:
        gnupghome, uid = gen_repo_key(repo_root)
        try:
            assert "Repo Signing Key" in uid
            assert os.path.basename(repo_root) in uid
        finally:
            cleanup_key(gnupghome)

    def test_cleanup_key_removes_homedir(self, repo_root: str) -> None:
        gnupghome, _ = gen_repo_key(repo_root)
        assert exists(gnupghome)
        cleanup_key(gnupghome)
        assert not exists(gnupghome)

    def test_export_public_key_writes_armored_file(
        self, repo_root: str, tempdir: str,
    ) -> None:
        gnupghome, uid = gen_repo_key(repo_root)
        try:
            dest = join(tempdir, "repo.asc")
            export_public_key(gnupghome, uid, dest)
            assert exists(dest)
            with open(dest) as fob:
                assert "BEGIN PGP PUBLIC KEY BLOCK" in fob.read()
        finally:
            cleanup_key(gnupghome)

    def test_gen_and_sign_creates_repo_asc(self, indexed_root: str) -> None:
        repo = Repository(indexed_root, "trixie", "pool", "1.0", "origin")
        gen_and_sign(repo)
        assert exists(join(indexed_root, "repo.asc"))

    def test_gen_and_sign_creates_signed_release_files(
        self, indexed_root: str,
    ) -> None:
        repo = Repository(indexed_root, "trixie", "pool", "1.0", "origin")
        gen_and_sign(repo)
        dist_dir = join(indexed_root, "dists", "trixie")
        assert exists(join(dist_dir, "Release"))
        assert exists(join(dist_dir, "Release.gpg"))
        assert exists(join(dist_dir, "InRelease"))

    def test_gen_and_sign_cleans_up_homedir(
        self,
        indexed_root: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Track the temp dir created by gen_repo_key and verify it is removed
        # even though gen_and_sign's finally block handles cleanup internally.
        created: list[str] = []
        real_mkdtemp = tempfile.mkdtemp

        def tracking_mkdtemp(*_args: object, **_kwargs: object) -> str:
            path = real_mkdtemp()
            created.append(path)
            return path

        monkeypatch.setattr("repo_lib.gpg.tempfile.mkdtemp", tracking_mkdtemp)
        repo = Repository(indexed_root, "trixie", "pool", "1.0", "origin")
        gen_and_sign(repo)

        assert created, "gen_repo_key never called mkdtemp"
        for d in created:
            assert not exists(d), f"private key homedir not cleaned up: {d}"


class TestGpgCli:
    def test_cli_release_gen_key_creates_repo_asc(
        self, indexed_root: str,
    ) -> None:
        result = run_repo("release", indexed_root, "trixie", "--gen-key")
        assert result.returncode == 0
        assert exists(join(indexed_root, "repo.asc"))
        dist_dir = join(indexed_root, "dists", "trixie")
        assert exists(join(dist_dir, "Release.gpg"))
        assert exists(join(dist_dir, "InRelease"))

    def test_cli_release_gen_key_and_gpgkey_are_mutually_exclusive(
        self, indexed_root: str,
    ) -> None:
        result = run_repo(
            "release", indexed_root, "trixie",
            "--gen-key", "--gpgkey", "somekeyid",
        )
        assert result.returncode != 0

    def test_cli_release_key_expiry_sets_expiry(
        self, indexed_root: str,
    ) -> None:
        # Verify --key-expiry is accepted and the command succeeds.
        result = run_repo(
            "release", indexed_root, "trixie",
            "--gen-key", "--key-expiry", "1d",
        )
        assert result.returncode == 0
        assert exists(join(indexed_root, "repo.asc"))


class TestClientConfigLib:
    def test_write_creates_sources_file(
        self, repo_with_asc: str, tempdir: str,
    ) -> None:
        name = "testrepo"
        write_client_config(
            repo_with_asc, "trixie", "main", "amd64",
            uri="https://repo.example.com",
            output_dir=tempdir,
            name=name,
        )
        assert exists(join(tempdir, f"{name}.sources"))

    def test_write_copies_asc_to_output(
        self, repo_with_asc: str, tempdir: str,
    ) -> None:
        name = "myrepo"
        write_client_config(
            repo_with_asc, "trixie", "main", "amd64",
            uri="https://repo.example.com",
            output_dir=tempdir,
            name=name,
        )
        assert exists(join(tempdir, f"{name}.asc"))

    def test_sources_file_has_correct_content(
        self, repo_with_asc: str, tempdir: str,
    ) -> None:
        name = "myrepo"
        write_client_config(
            repo_with_asc, "trixie", "main", "amd64",
            uri="https://repo.example.com",
            output_dir=tempdir,
            name=name,
        )
        with open(join(tempdir, f"{name}.sources")) as fob:
            content = fob.read()
        assert "Types: deb\n" in content
        assert "URIs: https://repo.example.com\n" in content
        assert "Suites: trixie\n" in content
        assert "Components: main\n" in content
        assert "Architectures: amd64\n" in content
        assert f"Signed-By: /usr/share/keyrings/{name}.asc\n" in content

    def test_default_name_from_basename(
        self, repo_with_asc: str, tempdir: str,
    ) -> None:
        expected_name = os.path.basename(repo_with_asc)
        write_client_config(
            repo_with_asc, "trixie", "main", "amd64",
            uri="https://repo.example.com",
            output_dir=tempdir,
        )
        assert exists(join(tempdir, f"{expected_name}.sources"))
        assert exists(join(tempdir, f"{expected_name}.asc"))

    def test_custom_name_used_for_output_files(
        self, repo_with_asc: str, tempdir: str,
    ) -> None:
        write_client_config(
            repo_with_asc, "trixie", "main", "amd64",
            uri="https://repo.example.com",
            output_dir=tempdir,
            name="custom-name",
        )
        assert exists(join(tempdir, "custom-name.sources"))
        assert exists(join(tempdir, "custom-name.asc"))

    def test_missing_repo_asc_raises(
        self, repo_root: str, tempdir: str,
    ) -> None:
        # repo_root has no repo.asc; write_client_config must raise RepoError.
        with pytest.raises(RepoError, match=r"repo\.asc not found"):
            write_client_config(
                repo_root, "trixie", "main", "amd64",
                uri="https://repo.example.com",
                output_dir=tempdir,
            )


class TestClientConfigCli:
    def test_cli_client_config_missing_uri_exits_nonzero(
        self, repo_with_asc: str,
    ) -> None:
        result = run_repo(
            "client-config", repo_with_asc, "trixie", "main", "amd64",
        )
        assert result.returncode != 0

    def test_cli_client_config_missing_args_exits_nonzero(self) -> None:
        result = run_repo("client-config")
        assert result.returncode != 0

    def test_cli_client_config_success(
        self, repo_with_asc: str, tempdir: str,
    ) -> None:
        result = run_repo(
            "client-config", repo_with_asc, "trixie", "main", "amd64",
            "--uri", "https://repo.example.com",
            "--output", tempdir,
            "--name", "testrepo",
        )
        assert result.returncode == 0
        assert exists(join(tempdir, "testrepo.sources"))
        assert exists(join(tempdir, "testrepo.asc"))

    def test_cli_client_config_missing_repo_asc_exits_nonzero(
        self, repo_root: str, tempdir: str,
    ) -> None:
        result = run_repo(
            "client-config", repo_root, "trixie", "main", "amd64",
            "--uri", "https://repo.example.com",
            "--output", tempdir,
        )
        assert result.returncode != 0
