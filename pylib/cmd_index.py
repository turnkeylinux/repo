#!/usr/bin/python
"""Index repository component

Arguments:
  path          path to repository
  release       release to act on
  component     release component to index

"""

import sys
import getopt

import help

from repo import Repository

@help.usage(__doc__)
def usage():
    print >> sys.stderr, "Syntax: %s <path> <release> <component>" % sys.argv[0]

def main():
    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], "", [])
    except getopt.GetoptError, e:
        usage(e)

    if not args:
        usage()

    if len(args) != 3:
        usage("bad number of arguments")

    path, release, component = args

    repo = Repository(path, release)
    repo.index(component)

if __name__ == "__main__":
    main()

