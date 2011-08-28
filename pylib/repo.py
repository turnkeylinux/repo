
import os
from os.path import *

import executil

class Error(Exception):
    pass

class Repository:
    def __init__(self, path, release, version='1.0', origin='TurnKey'):
        if not exists(path):
            raise Error('repository does not exist', path)

        self.path = path
        self.release = release
        self.version = version
        self.origin = origin

    def _archive_cmd(self, command, input, output):
        cwd = os.getcwd()
        os.chdir(self.path)
        executil.system('apt-ftparchive %s %s > %s' % (command, input, output))
        os.chdir(cwd)

    def index(self, component):
        component_dir = join('pool', component)
        if not exists(join(self.path, component_dir)):
            raise Error('component does not exist', join(self.path, component_dir))

        output_dir = join(self.path, 'dists', self.release, component, 'binary-i386')
        if not exists(output_dir):
            os.makedirs(output_dir)
        
        self._archive_cmd('packages', component_dir, join(output_dir, 'Packages'))

        fh = file(join(output_dir, 'Release'), "w")
        print >> fh, "Origin: %s" % self.origin
        print >> fh, "Label: %s" % self.origin
        print >> fh, "Archive: %s" % self.release
        print >> fh, "Version: %s" % self.version
        print >> fh, "Component: %s" % component
        fh.close()

