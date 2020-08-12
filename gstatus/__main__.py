#!/usr/bin/env python3

from optparse import OptionParser
from distutils.version import LooseVersion as version
from shutil import get_terminal_size

try:
    # If imported directly from the same directory
    from glusterlib.cluster import Cluster
    from glusterlib.display_status import display_status
    import version as gstatus_version
except ImportError:
    # when installed using setup.py
    from gstatus.glusterlib.cluster import Cluster
    from gstatus.glusterlib.display_status import display_status
    import gstatus.version as gstatus_version

supported_version = "3.12"

def check_version(cluster):
    """Check the gluster version, exit if less than 3.12"""
    if version(cluster.glusterfs_version) < version(supported_version):
        print("gstatus: GlusterFS %s is not supported, use GlusterFS %s "
              "or above." %(glusterfs_version, supported_version))
        exit(1)

def parse_options():

    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage,
                          version="%prog " + gstatus_version.VERSION)

    parser.add_option("-v", "--volume", dest="volumes", action="store_true",
                      default=False,
                      help="Supply a volume or a list of volumes by repeated"
                      " invocation of -v. A regular expression can be provided"
                      " in place of a volume name (ensure to use single quotes"
                      " around the expression)")
    parser.add_option("-a", "--all", dest="alldata", action="store_true",
                      default=False,
                      help="Print all available details on volumes")
    parser.add_option("-b", "--bricks", dest="brickinfo", action="store_true",
                      default=False,
                      help="Print the list of bricks")
    parser.add_option("-q", "--quota", dest="displayquota", action="store_true",
                      default=False,
                      help="Print the quota information")
    parser.add_option("-s", "--snapshots", dest="displaysnap",
                      action="store_true", default=False,
                      help="Print the snapshot information")
    parser.add_option("-u", "--units", dest="units",
                      choices=['h', 'k', 'm', 'g', 't', 'p'],
                      help="display storage size in given units")
    return(parser.parse_args())


def main():
    options, args = parse_options()
    cluster = Cluster(options, args)
    check_version(cluster)
    cluster.gather_data()
    display_status(cluster)

if __name__ == '__main__':
    main()
