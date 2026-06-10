"""GPG key generation and export for repository release signing."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from os.path import basename, join
from typing import TYPE_CHECKING

from repo_lib import RepoError

if TYPE_CHECKING:
    from repo_lib import Repository

logger = logging.getLogger(__name__)


def _gpg(args: list[str], gnupghome: str) -> str:
    """Run a gpg command in gnupghome; raise RepoError on failure."""
    cmd = ["/usr/bin/gpg", "--homedir", gnupghome, *args]
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RepoError(result.stderr)
    return result.stdout


def gen_repo_key(
    repo_path: str,
    expiry: str = "10y",
) -> tuple[str, str]:
    """Generate a 4096-bit RSA signing key in a fresh temporary GPG homedir.

    Returns (gnupghome, uid). The caller must pass gnupghome to cleanup_key
    after signing is complete so the private key is not retained on disk.
    """
    gnupghome = tempfile.mkdtemp()
    os.chmod(gnupghome, 0o700)
    uid = f"Repo Signing Key <repo@{basename(repo_path.rstrip('/'))}>"
    logger.debug(
        "Generating rsa4096 key (expiry=%s) in: %s", expiry, gnupghome,
    )
    _gpg(
        [
            "--batch",
            "--pinentry-mode",
            "loopback",
            "--passphrase",
            "",
            "--quick-generate-key",
            uid,
            "rsa4096",
            "sign",
            expiry,
        ],
        gnupghome,
    )
    return gnupghome, uid


def export_public_key(gnupghome: str, uid: str, dest: str) -> None:
    """Export the public key as an ASCII-armored file at dest."""
    logger.debug("Exporting public key to: %s", dest)
    _gpg(
        ["--armor", "--export", "--output", dest, uid],
        gnupghome,
    )


def cleanup_key(gnupghome: str) -> None:
    """Delete the temporary GPG homedir, removing the private key."""
    shutil.rmtree(gnupghome, ignore_errors=True)
    logger.debug("Deleted temporary GPG homedir: %s", gnupghome)


def gen_and_sign(repo: Repository, expiry: str = "10y") -> None:
    """Generate a temporary key, sign the release, export repo.asc, clean up.

    The private key is always deleted before this function returns, even if
    signing or export fails.
    """
    gnupghome, uid = gen_repo_key(repo.path, expiry)
    try:
        repo.generate_release(uid, gnupghome)
        export_public_key(gnupghome, uid, join(repo.path, "repo.asc"))
    finally:
        # Always remove the private key even if signing or export fails.
        cleanup_key(gnupghome)
