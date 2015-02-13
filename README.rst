Tools to index and create a Debian package repository
=====================================================

Usage
-----

::

    $ repo

    version 1.0 (c) TurnKey GNU/Linux - http://www.turnkeylinux.org
    Syntax: repo <command> [args]
    Tools to index and create a Debian package repository

    Commands:

        index      Index repository component
        release    Generate repository release

    $ repo-index -h
    Syntax: index [-options] <path> <release> <component> <arch>
    Index repository component

    Arguments:

      path          Path to repository
      release       Release to act on
      component     Release component to index
      arch          Architecture (e.g., i386, amd64)

    Options:
      --pool=       Packages pool directory (default: pool)
      --origin=     Origin to set (default: turnkeylinux)
      --version=    Release version to set (default: 1.0)

    $ repo-release 
    Syntax: release [-options] <path> <release>
    Generate repository release
    
    Arguments:
      path          Path to repository
      release       Release to act on
    
    Options:
      --gpgkey=     GPG Key to use when signing the release
      --pool=       Packages pool directory (default: pool)
      --origin=     Origin to set (default: turnkeylinux)
      --version=    Release version to set (default: 1.0)
