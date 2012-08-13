#!/usr/bin/python
"""Index repository component

Arguments:
  path          Path to repository
  release       Release to act on
  component     Release component to index

Options:
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
    print >> sys.stderr, "Syntax: %s [-options] <path> <release> <component>" % sys.argv[0]

def main():
    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], "", 
                                       ['pool=', 'origin=', 'version='])
    except getopt.GetoptError, e:
        usage(e)

    kws = {}
    for opt, val in opts:
        kws[opt[2:]] = val

    if not args:
        usage()

    if len(args) != 3:
        usage("bad number of arguments")

    path, release, component = args

    repo = Repository(path, release, **kws)
    repo.index(component)

if __name__ == "__main__":
    main()

