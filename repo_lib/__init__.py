# Copyright (c) 2021 TurnKey GNU/Linux - https://www.turnkeylinux.org
#
# This file is part of Repo
#
# Repo is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.

import subprocess
import os
from os.path import exists, join, isdir, basename
from typing import Set, Optional
import logging

logger = logging.getLogger(__name__)

level = os.getenv('REPO_LOG_LEVEL', '').lower()
env_debug = os.getenv("DEBUG")

# allow 'DEBUG' env var to override 'REPO_LOG_LEVEL'
if 'DEBUG' in os.environ.keys():
    level = 'debug'

loglevel = logging.INFO  # default logging / fallback if unknown log level
logformat = ('%(asctime)s - [%(levelname)-7s]'
            ' %(filename)s:%(lineno)4d %(message)s')

if level == 'debug':
    loglevel = logging.DEBUG
    logformat = (
            '%(asctime)s - [%(levelname)-7s]'
            ' %(filename)s:%(lineno)4d %(funcName)15s(): - %(message)s'
            )
elif level in ('warn', 'warning', "default"):
    loglevel = logging.WARNING
elif level in ('err', 'error', 'fatal'):
    loglevel = logging.ERROR

logging.basicConfig(
    format=logformat,
    level=loglevel
    )


class RepoError(Exception):
    pass


class Repository:

    def __init__(self,
                 path: str,
                 release: str,
                 pool: str,
                 version: str,
                 origin: str):
        if not exists(path):
            raise RepoError(f"repository {path} does not exist")
        self.path = path
        self.release = release
        self.pool = pool
        self.version = version
        self.origin = origin

    def _archive_cmd(self, command: str, input: str, arch: str = '') -> str:
        logger.debug(f"{command=}, {input=}, {arch=}")
        cwd = os.getcwd()
        os.chdir(self.path)
        cmd = ["apt-ftparchive", command, input]
        if arch:
            cmd.insert(1, f"--arch={arch}")
        logger.debug(f"Running: {' '.join(cmd)}")
        output = subprocess.run(cmd, text=True, capture_output=True)
        os.chdir(cwd)
        log_stdout = "\n".join(output.stdout.split("\n")[:20])+"\n..."
        logger.debug(f"stdout (abridged):\n{log_stdout}")
        return output.stdout

    def index(self, component: str, arch: str) -> None:
        logger.debug(f"({component=}, {arch=})")
        component_dir = join(self.pool, component)
        if not exists(join(self.path, component_dir)):
            raise RepoError(
                f"component '{join(self.path, component_dir)}' does not exist"
                )

        output_dir = join(
                self.path,
                "dists",
                self.release,
                component,
                f"binary-{arch}"
                )

        os.makedirs(output_dir, exist_ok=True)

        output = self._archive_cmd("packages", component_dir, arch=arch)
        packages_file = join(output_dir, "Packages")
        logger.debug(f"Writing: {packages_file}")
        with open(packages_file, "w") as fob:
            if output:
                output += '\n'
            fob.write(output)

        for zip in ["gzip", "bzip2", "xz"]:
            zip_cmd = [join("/usr/bin", zip), "-k", join(output_dir, "Packages")]
            logger.debug(f"Running: {' '.join(zip_cmd)}")
            subprocess.run(zip_cmd)

        release_file = join(output_dir, 'Release')
        logger.debug(f"Writing: {release_file}")
        with open(release_file, "w") as fob:
            fob.writelines(
                [
                    f"Archive: {self.release}\n",
                    f"Origin: {self.origin}\n",
                    f"Label: {self.origin}\n",
                    f"Version: {self.version}\n",
                    # TODO implement "Acquire-By-Hash"
                    # f"Acquire-By-Hash: yes\n",
                    f"Component: {component}\n",
                    f"Architecture: {arch}\n"
                 ]
                )

    def generate_release(self, gpgkey: Optional[str] = None):
        logger.debug(f"{gpgkey=}")
        def get_archs() -> Set[str]:
            archs = set()
            dist_path = join(self.path, 'dists', self.release)
            for component in os.listdir(dist_path):
                component_path = join(dist_path, component)
                if not isdir(component_path):
                    continue

                for binary in os.listdir(component_path):
                    archs.add(binary.replace('binary-', ''))
            logger.debug(f"Return: {archs=}")
            return archs

        components_dir = join(self.path, self.pool)
        release_dir = join('dists', self.release)

        release_file = join(self.path, release_dir, 'Release')
        release_gpg = join(self.path, release_dir, 'Release.gpg')

        for path in (release, release_gpg):
            if exists(path):
                os.remove(path)

        hashes = self._archive_cmd('release', release_dir)
        day = datetime.now(timezone.utc).strftime("%d %b %Y")
        date_time = datetime.now(timezone.utc).strftime(
                            "%a, %d %b %Y %H:%M:%S UTC"
                            )
        logger.debug(f"Writing: {release_file}")
        with open(release_file, "w") as fob:
            fob.writelines(
                [
                    f"Origin: {self.origin}\n",
                    f"Label: {self.origin}\n",
                    f"Suite: {self.release}\n",
                    f"Version: {self.version}\n",
                    f"Codename: {self.release}\n",
                    # TODO url for pkg changelogs & other metadata
                    # f"Changelogs: CHANGELOG_URL_GOES_HERE",
                    f"Date: {date_time}\n",
                    # TODO implement "Acquire-By-Hash"
                    # f"Acquire-By-Hash: yes\n",
                    # TODO need to look at this more closely; my reading
                    #   suggests that this might make 'apt update' quicker
                    # f"No-Support-for-Architecture-all: Packages\n",
                    f"Architectures: {' '.join(get_archs())}\n",
                    f"Components: {' '.join(os.listdir(components_dir))}\n",
                    f"Description: {self.origin} {self.release}"
                    f" {self.version} Released {day}\n",
                    f"{hashes}\n"])

        if gpgkey:
            try:
                gpg_cmd = ["/usr/bin/gpg", "-abs", "-u", gpgkey,
                           "-o", release_gpg, release]
                logger.debug(f"Running: {' '.join(gpg_cmd)}")
                subprocess.run(gpg_cmd, check=True)
            except CalledProcessError as e:
                raise RepoError(e) from e
