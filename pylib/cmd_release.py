#!/usr/bin/python
"""Generate repository release

Arguments:
  path          Path to repository
  release       Release to act on

Options:
  --gpgkey=     GPG Key to use when signing the release
  --pool=       Pool directory (default: pool)
  --origin=     Origin to set (default: TurnKey)
  --version=    Release version to set (default: 1.0)

"""

import sys
import getopt

import help

from repo import Repository

@help.usage(__doc__)
def usage():
    print >> sys.stderr, "Syntax: %s [-options] <path> <release>" % sys.argv[0]

def main():
    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], "", 
                                       ['gpgkey=', 'pool=', 'origin=', 'version='])
    except getopt.GetoptError, e:
        usage(e)

    kws = {}
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

