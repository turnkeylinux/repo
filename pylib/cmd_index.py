#!/usr/bin/python
# Copyright (c) TurnKey Linux - http://www.turnkeylinux.org
#
# This file is part of Repo
#
# Repo is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.

"""Index repository component

Arguments:
  path          Path to repository
  release       Release to act on
  component     Release component to index
  arch          Architecture (e.g., i386, amd64)

Options:
  --pool=       Packages pool directory (default: pool)
  --origin=     Origin to set (default: turnkeylinux)
  --version=    Release version to set (default: 1.0)

"""

import sys
import getopt

import help

from repo import Repository

@help.usage(__doc__)
def usage():
    s = "Syntax: %s [-options] <path> <release> <component> <arch>" % sys.argv[0]
    print >> sys.stderr, s

def main():
    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], "", 
                                       ['pool=', 'origin=', 'version='])
    except getopt.GetoptError, e:
        usage(e)

    kws = {'pool': 'pool', 'version': '1.0', 'origin': 'turnkeylinux'}
    for opt, val in opts:
        kws[opt[2:]] = val

    if not args:
        usage()

    if len(args) != 4:
        usage("bad number of arguments")

    path, release, component, arch = args

    repo = Repository(path, release, **kws)
    repo.index(component, arch)

if __name__ == "__main__":
    main()

