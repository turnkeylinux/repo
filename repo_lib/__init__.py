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
from os.path import exists, join
import gzip
import bz2
import shutil
from typing import Set, Optional


class RepoError(Exception):
    pass


class Repository:
    def __init__(self, path: str, release: str, pool: str,
                 version: str, origin: str):
        if not exists(path):
            raise RepoError('repository does not exist', path)

        self.path = path
        self.release = release
        self.pool = pool
        self.version = version
        self.origin = origin

    def _archive_cmd(self, command: str, input: str, arch: str = '') -> str:
        cwd = os.getcwd()
        os.chdir(self.path)
        com = ['apt-ftparchive', command, input]
        if arch:
            com.insert(1, f'--arch={arch}')
        output = subprocess.run(['apt-ftparchive', command, input],
                                text=True, capture_output=True)
        os.chdir(cwd)
        return output.stdout

    def index(self, component: str, arch: str):
        component_dir = join(self.pool, component)
        if not exists(join(self.path, component_dir)):
            raise RepoError('component does not exist',
                            join(self.path, component_dir))

        output_dir = join(self.path, 'dists', self.release,
                          component, f'binary-{arch}')

        if not exists(output_dir):
            os.makedirs(output_dir)

        output = self._archive_cmd('packages', component_dir, arch=arch)
        with open(join(output_dir, 'Packages'), "w") as fob:
            if output:
                output += '\n'
            fob.write(output)

        with open(join(output_dir, 'Packages'), 'rb') as fob:
            with gzip.open(join(output_dir, 'Packages.gz'), 'wb') as zob:
                zob.writelines(fob)
            with bz2.open(join(output_dir, 'Packages.bz2'), 'wb') as zob:
                zob.writelines(fob)

        with open(join(output_dir, 'Release'), "w") as fob:
            fob.writelines(
                [f"Origin: {self.origin}\n",
                 f"Label: {self.origin}\n",
                 f"Archive: {self.release}\n",
                 f"Version: {self.version}\n",
                 f"Component: {component}\n",
                 f"Architecture: {arch}\n"])

    def generate_release(self, gpgkey: Optional[str] = None):
        def get_archs() -> Set[str]:
            archs = set()
            dist_path = join(self.path, 'dists', self.release)
            for component in os.listdir(dist_path):
                component_path = join(dist_path, component)
                if not isdir(component_path):
                    continue

                for binary in os.listdir(component_path):
                    if binary == 'binary-all':
                        continue
                    archs.add(binary.replace('binary-', ''))

            return archs

        components_dir = join(self.path, self.pool)
        release_dir = join('dists', self.release)

        release = join(self.path, release_dir, 'Release')
        release_gpg = join(self.path, release_dir, 'Release.gpg')

        for path in (release, release_gpg):
            if exists(path):
                os.remove(path)

        hashes = self._archive_cmd('release', release_dir)
        with open(release, "w") as fob:
            fob.writelines(
                [f"Origin: {self.origin}\n",
                 f"Label: {self.origin}\n",
                 f"Suite: {self.release}\n",
                 f"Version: {self.version}\n",
                 f"Codename: {self.release}\n",
                 f"Architectures: {' '.join(get_archs())}\n",
                 f"Components: {' '.join(os.listdir(components_dir))}\n",
                 f"Description: {self.origin} {self.release} {self.version}\n",
                 f"{hashes}\n"])

        if gpgkey:
            subprocess.run(["gpg", "-abs", f"-u {gpgkey}",
                            f"-o {release_gpg}", release],
                           text=True)
