Tools to index and create a Debian package repository
=====================================================

Populates a pool with .deb files, indexes the pool, generates a signed
Release file, and produces client apt configuration.

Commands
--------

repo download
~~~~~~~~~~~~~

Resolve and download packages into the pool.

::

    repo download [-options] <path> <release> <component> <arch>
                  <package> [<package> ...]

    Arguments:
      path          Path to repository
      release       Release to target (e.g. trixie)
      component     Pool component (e.g. main)
      arch          Architecture (e.g. amd64)
      package       One or more packages to resolve and download

    Options:
      --pool=       Pool directory (default: pool)
      --chroot=     Path to target rootfs chroot (default: none, use host)

Resolves the full recursive Depends closure via ``apt-cache depends
--recurse``. Subtracts packages already installed in the target
environment via ``dpkg-query``. Downloads the remainder via ``apt-get
install --download-only`` and copies the .deb files into the pool.
Recommends, Suggests, Conflicts, Breaks, Replaces, and Enhances are not
followed. Virtual packages are skipped.

When ``--chroot`` is provided, ``apt-cache``, ``dpkg-query``, and
``apt-get`` run inside the chroot via turnkey-chroot, and .deb files are
copied from the chroot's apt cache.

repo index
~~~~~~~~~~

Index a pool component and write the Packages files.

::

    repo index [-options] <path> <release> <component> [<arch>]

    Arguments:
      path          Path to repository
      release       Release to act on (e.g. trixie)
      component     Release component to index (e.g. main)
      arch          Architecture (default: host arch)

    Options:
      --pool=       Pool directory (default: pool)
      --origin=     Origin to set (default: turnkeylinux)
      --version=    Release version to set (default: 1.0)

repo release
~~~~~~~~~~~~

Generate the repository Release file, optionally signed.

::

    repo release [-options] <path> <release>

    Arguments:
      path          Path to repository
      release       Release to act on (e.g. trixie)

    Options:
      --pool=       Pool directory (default: pool)
      --origin=     Origin to set (default: turnkeylinux)
      --version=    Release version to set (default: 1.0)
      --gpgkey=     GPG key fingerprint or uid to sign with
      --gen-key     Generate a temporary 4096-bit RSA signing key
      --key-expiry= Key expiry for --gen-key (default: 10y)

``--gpgkey`` and ``--gen-key`` are mutually exclusive. When ``--gen-key``
is used, a passphraseless RSA key is generated in a temporary GPG homedir,
the release is signed, the public key is exported as ``repo.asc`` in the
repository root, and the private key is deleted. The key is not retained
after the command exits.

repo client-config
~~~~~~~~~~~~~~~~~~

Generate client apt configuration files for distribution to end systems.

::

    repo client-config [-options] <path> <release> <component> <arch>

    Arguments:
      path          Path to repository
      release       Release (e.g. trixie)
      component     Component (e.g. main)
      arch          Architecture (e.g. amd64)

    Options:
      --pool=       Pool directory (default: pool)
      --uri=        Repo URI as clients will access it (required)
      --output=     Output directory (default: current directory)
      --name=       Base name for output files (default: repo path basename)

Writes a deb822 ``.sources`` file and copies ``repo.asc`` into the output
directory. The ``.sources`` file references the signing key at
``/usr/share/keyrings/<name>.asc`` via ``Signed-By``. Requires
``repo.asc`` to exist in the repository root (run ``repo release
--gen-key`` first).

Output files are standalone and intended for placement into
``/usr/share/keyrings/`` and ``/etc/apt/sources.list.d/`` on client
systems.

Typical workflow
----------------

::

    # Populate the pool
    repo download /srv/repo trixie main amd64 curl wget

    # Index the component
    repo index /srv/repo trixie main amd64

    # Generate a signed release (key exported to /srv/repo/repo.asc)
    repo release /srv/repo trixie --gen-key

    # Generate client configuration
    repo client-config /srv/repo trixie main amd64 \
        --uri https://repo.example.com \
        --output /tmp/repo-client \
        --name myrepo

    # On each client system:
    cp myrepo.asc /usr/share/keyrings/
    cp myrepo.sources /etc/apt/sources.list.d/
    apt update
