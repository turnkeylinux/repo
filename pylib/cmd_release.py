#!/usr/bin/python
# Copyright (c) TurnKey GNU/Linux - http://www.turnkeylinux.org
#
# This file is part of Repo
#
# Repo is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.

"""Generate repository release

Arguments:
  path          Path to repository
  release       Release to act on

Options:
  --gpgkey=     GPG Key to use when signing the release
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
    s = "Syntax: %s [-options] <path> <release>" % sys.argv[0]
    print >> sys.stderr, s

def main():
    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], "", 
                                       ['gpgkey=', 'pool=', 'origin=', 'version='])
    except getopt.GetoptError, e:
        usage(e)

    kws = {'pool': 'pool', 'version': '1.0', 'origin': 'turnkeylinux'}
    gpgkey = None
    for opt, val in opts:
        if opt == '--gpgkey':
            gpgkey = val
        else:
            kws[opt[2:]] = val

    if not args:
        usage()

    if len(args) != 2:
        usage("bad number of arguments")

    path, release = args

    repo = Repository(path, release, **kws)
    repo.generate_release(gpgkey)

if __name__ == "__main__":
    main()

