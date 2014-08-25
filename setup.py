#!/usr/bin/python

from setuptools import setup
import distutils.command.install_scripts
import shutil

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
    version= "0.61",
    description= "Show the current health of the elements in a Gluster Trusted Pool",
    long_description = long_description,
    author = "Paul Cuzner",
    author_email = "pcuzner@redhat.com",
    url = "https://forge.gluster.org/gstatus",
    license = "GPLv3",
    packages = [
        "gstatus",
        "gstatus.classes",
        "gstatus.functions"
    ],
    scripts = [ "gstatus.py" ],
    cmdclass = {
        "install_scripts" : strip_py_ext
    }
)
