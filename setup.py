#!/usr/bin/python3

from distutils.core import setup

setup(
    name="repo",
    version="2.0rc1",
    author="Jeremy Davis",
    author_email="jeremy@turnkeylinux.org",
    url="https://github.com/turnkeylinux/repo",
    packages=["repo_lib"],
    scripts=["repo"]
)
