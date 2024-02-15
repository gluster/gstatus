#!/usr/bin/python

from setuptools import setup
import shutil

from gstatus import version

f = open('README.md')
long_description = f.read().strip()
f.close()

setup(
    name = "gstatus",
    version= version.VERSION,
    description= "Show the health of the components in a glusterfs Trusted Storage Pool",
    long_description = long_description,
    author = "Paul Cuzner",
    author_email = "pcuzner@redhat.com",
    url = "https://github.com/gluster/gstatus",
    license = "GPLv3",
    install_requires=['glustercli', 'packaging'],
    packages = [
        "gstatus",
        "gstatus.glusterlib",
        ],
    entry_points={
        "console_scripts": [
            "gstatus = gstatus.__main__:main",
        ]
    }
)
