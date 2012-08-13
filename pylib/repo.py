
import os
from os.path import *

import executil

class Error(Exception):
    pass

class Repository:
    def __init__(self, path, release, pool='pool' ,version='1.0', origin='TurnKey'):
        if not exists(path):
            raise Error('repository does not exist', path)

        self.path = path
        self.release = release
        self.pool = pool
        self.version = version
        self.origin = origin

    def _archive_cmd(self, command, input):
        cwd = os.getcwd()
        os.chdir(self.path)
        output = executil.getoutput('apt-ftparchive %s %s' % (command, input))
        os.chdir(cwd)
        return output

    def index(self, component):
        component_dir = join(self.pool, component)
        if not exists(join(self.path, component_dir)):
            raise Error('component does not exist', join(self.path, component_dir))

        output_dir = join(self.path, 'dists', self.release, component, 'binary-i386')
        if not exists(output_dir):
            os.makedirs(output_dir)

        output = self._archive_cmd('packages', component_dir)
        fh = file(join(output_dir, 'Packages'), "w")
        fh.write(output)
        if output:
            # append newline if packages were in pool
            print >> fh
        fh.close()

        executil.system("gzip -c %s > %s" % (join(output_dir, 'Packages'),
                                             join(output_dir, 'Packages.gz')))

        fh = file(join(output_dir, 'Release'), "w")
        print >> fh, "Origin: %s" % self.origin
        print >> fh, "Label: %s" % self.origin
        print >> fh, "Archive: %s" % self.release
        print >> fh, "Version: %s" % self.version
        print >> fh, "Component: %s" % component
        fh.close()

    def generate_release(self, gpgkey=None):
        components_dir = join(self.path, self.pool)
        release_dir = join('dists', self.release)

        release = join(self.path, release_dir, 'Release')
        release_gpg = join(self.path, release_dir, 'Release.gpg')
        
        for path in (release, release_gpg):
            if exists(path):
                os.remove(path)

        hashes = self._archive_cmd('release', release_dir)

        fh = file(release, "w")
        print >> fh, "Origin: %s" % self.origin
        print >> fh, "Label: %s" % self.origin
        print >> fh, "Suite: %s" % self.release
        print >> fh, "Version: %s" % self.version
        print >> fh, "Codename: %s" % self.release
        print >> fh, "Architectures: i386"
        print >> fh, "Components: %s" % ' '.join(os.listdir(components_dir))
        print >> fh, "Description: %s %s %s" % (self.origin,
                                                self.release,
                                                self.version)
        print >> fh, hashes
        fh.close()

        if gpgkey:
            cmd = "gpg -abs -u %s -o %s %s" % (gpgkey, release_gpg, release)
            executil.system(cmd)


