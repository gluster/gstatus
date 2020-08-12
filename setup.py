#!/usr/bin/python

from setuptools import setup
import distutils.command.install_scripts
import shutil

from gstatus import version

f = open('README')
long_description = f.read().strip()
f.close()

# idea from http://stackoverflow.com/a/11400431/2139420
class strip_py_ext(distutils.command.install_scripts.install_scripts):
    def run(self):
        distutils.command.install_scripts.install_scripts.run(self)
        for script in self.get_outputs():
            if script.endswith(".py"):
                shutil.move(script, script[:-3])


setup(
    name = "gstatus",
    version= version.VERSION,
    description= "Show the health of the components in a glusterfs Trusted Storage Pool",
    long_description = long_description,
    author = "Paul Cuzner",
    author_email = "pcuzner@redhat.com",
    url = "https://github.com/gluster/gstatus",
    license = "GPLv3",
    install_requires=['glustercli'],
    packages = [
        "gstatus",
        "gstatus.glusterlib",
        ],
    entry_points={
        "console_scripts": [
            "gstatus = gstatus.__main__:main",
        ]
    },
    cmdclass = {
        "install_scripts" : strip_py_ext
    }
)
