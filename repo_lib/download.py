"""Dependency resolution and pool population for a Debian package repo."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from os.path import exists, join

from repo_lib import RepoError

logger = logging.getLogger(__name__)

APT_CACHE = "/var/cache/apt/archives"


def _run(cmd: list[str], chroot: str = "") -> str:
    """Run a command on the host or inside a chroot; return stdout."""
    if chroot:
        # Imported here so the package is only required when --chroot is used.
        from chroot import Chroot  # type: ignore[import-untyped]  # noqa: PLC0415, I001
        result = Chroot(chroot).run(
            cmd, capture_output=True, text=True, check=False,
        )
    else:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False,
        )
    if result.returncode != 0:
        raise RepoError(result.stderr or result.stdout)
    return result.stdout


def resolve_deps(packages: list[str], chroot: str = "") -> set[str]:
    """Return the full recursive Depends closure for the given packages.

    Virtual packages (angle-bracketed in apt-cache output) are skipped.
    Recommends, Suggests, Conflicts, Breaks, Replaces and Enhances are
    excluded; only hard Depends and PreDepends are followed.
    """
    cmd = [
        "/usr/bin/apt-cache",
        "depends",
        "--recurse",
        "--no-recommends",
        "--no-suggests",
        "--no-conflicts",
        "--no-breaks",
        "--no-replaces",
        "--no-enhances",
        *packages,
    ]
    output = _run(cmd, chroot)
    deps: set[str] = set()
    for line in output.splitlines():
        # Non-indented lines without angle brackets are real package names.
        if line and not line[0].isspace() and "<" not in line:
            deps.add(line.strip())
    return deps


def installed_packages(chroot: str = "") -> set[str]:
    """Return the names of all packages installed in the environment."""
    cmd = [
        "/usr/bin/dpkg-query",
        "--showformat=${Package}\\n",
        "--show",
    ]
    output = _run(cmd, chroot)
    return {line.strip() for line in output.splitlines() if line.strip()}


def download_packages(packages: list[str], chroot: str = "") -> None:
    """Download packages into the apt cache via apt-get --download-only."""
    cmd = [
        "/usr/bin/apt-get",
        "install",
        "--download-only",
        "-y",
        *sorted(packages),
    ]
    _run(cmd, chroot)


def copy_debs_to_pool(pool_component: str, chroot: str = "") -> int:
    """Copy .deb files from the apt cache into pool_component.

    Files already present in the pool are skipped. Returns the count of
    files copied.
    """
    if chroot:
        cache_dir = join(chroot, "var", "cache", "apt", "archives")
    else:
        cache_dir = APT_CACHE
    count = 0
    for filename in os.listdir(cache_dir):
        if not filename.endswith(".deb"):
            continue
        src = join(cache_dir, filename)
        dst = join(pool_component, filename)
        if exists(dst):
            logger.debug("Already in pool: %s", filename)
            continue
        shutil.copy2(src, dst)
        logger.debug("Copied: %s", filename)
        count += 1
    return count


def populate_pool(
    path: str,
    pool: str,
    component: str,
    packages: list[str],
    chroot: str = "",
) -> None:
    """Resolve, download, and copy .deb files into pool/component.

    Reports totals at each stage. When chroot is given, apt-cache,
    dpkg-query, and apt-get run inside the chroot via turnkey-chroot,
    and .deb files are copied from the chroot's apt cache.
    """
    pool_component = join(path, pool, component)
    os.makedirs(pool_component, exist_ok=True)

    print(f"Resolving dependencies for: {', '.join(packages)}")
    resolved = resolve_deps(packages, chroot)
    print(f"Total packages in dependency closure: {len(resolved)}")

    installed = installed_packages(chroot)
    to_download = sorted(resolved - installed)
    already_installed = len(resolved) - len(to_download)
    print(
        f"Already installed (skipped): {already_installed},"
        f" to download: {len(to_download)}"
    )

    if not to_download:
        print("Nothing to download.")
        return

    logger.info("Downloading: %s", ", ".join(to_download))
    download_packages(to_download, chroot)

    count = copy_debs_to_pool(pool_component, chroot)
    print(f"Copied {count} .deb file(s) to pool.")
