"""Client apt configuration generation for a Debian package repository."""
from __future__ import annotations

import logging
import os
import shutil
from os.path import basename, exists, join

from repo_lib import RepoError

logger = logging.getLogger(__name__)


def write_client_config(
    path: str,
    release: str,
    component: str,
    arch: str,
    uri: str,
    output_dir: str = ".",
    name: str = "",
) -> None:
    """Write a deb822 .sources file and copy repo.asc into output_dir.

    The .sources file references the signing key at
    /usr/share/keyrings/<name>.asc via Signed-By. Output files are
    standalone and intended for placement into /usr/share/keyrings/ and
    /etc/apt/sources.list.d/ on client systems.
    """
    if not name:
        name = basename(path.rstrip("/"))

    asc_src = join(path, "repo.asc")
    if not exists(asc_src):
        raise RepoError(
            f"repo.asc not found in {path};"
            " run 'repo release --gen-key' first"
        )

    os.makedirs(output_dir, exist_ok=True)

    asc_dst = join(output_dir, f"{name}.asc")
    shutil.copy2(asc_src, asc_dst)
    logger.debug("Copied repo.asc to: %s", asc_dst)

    sources_path = join(output_dir, f"{name}.sources")
    logger.debug("Writing: %s", sources_path)
    with open(sources_path, "w") as fob:
        fob.writelines(
            [
                "Types: deb\n",
                f"URIs: {uri}\n",
                f"Suites: {release}\n",
                f"Components: {component}\n",
                f"Architectures: {arch}\n",
                f"Signed-By: /usr/share/keyrings/{name}.asc\n",
            ]
        )

    print(f"Written: {sources_path}")
    print(f"Written: {asc_dst}")
    print(
        f"Install: copy {name}.asc to /usr/share/keyrings/"
        f" and {name}.sources to /etc/apt/sources.list.d/"
    )
