
import os
from os.path import *

import executil

class Error(Exception):
    pass

class Repository:
    def __init__(self, path, release):
        if not exists(path):
            raise Error('repository does not exist', path)

        self.path = path
        self.release = release

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


