gstatus
=======

Overview
========
gstatus is a commandline utility to report the health and other statistics
related to a GlusterFS cluster. gstatus consolidates the volume, brick, and peer
information of a GlusterFS cluster.

At volume level, gstatus reports detailed infromation on quota usage, snapshots,
self-heal and rebalance status.

Motivation
==========
A gluster trusted storage pool (aka cluster), consists of several key
components viz. nodes, volumes, and bricks. In glusterfs, there isn't a single
command that can provide an overview of the cluster's health. This means that
administrators currently assess the cluster health by looking at several
commands to piece together a picture of the cluster's state.

This isn't ideal - so 'gstatus' is an attempt to provide an easy to use,
reliable, highlevel view of a cluster's health through a single command. The
tool gathers information by calling the glustercli library
(https://github.com/gluster/glustercli-python) and displays on the screen.

Dependencies
============
- python 3.0 or above
- gluster version 3.12 or above
- gluster CLI

Install
=======
Download the latest release with the command

```
$ curl -fsSL https://github.com/gluster/gstatus/releases/latest/download/install.sh | sudo bash -x
$ gstatus --version
```

Installating from source
========================
* Installing glustercli-python

```
git clone https://github.com/gluster/glustercli-python.git
cd glustercli-python
python3 setup.py install
```

Installing the gstatus tool:
* Using python-setuptools

```
git clone https://github.com/gluster/gstatus.git
cd gstatus
VERSION=1.0.6 make gen-version
python3 setup.py install
```

Running the tool
================

NOTE: The tool has to be run as root or sudo <cmd>. This requirement is
      imposed by gluster than gstatus. Since gstatus internally calls the
      gluster command, running as superuser is a necessity.

```
root@master-node:~# gstatus -h
Usage: gstatus [options]

Options:
  --version             show program's version number and exit
  -h, --help            show this help message and exit
  -v, --volume          volume info (default is ALL, or supply a volume name)
  -a, --all             Print all available details on volumes
  -b, --bricks          Print the list of bricks
  -q, --quota           Print the quota information
  -s, --snapshots       Print the snapshot information
  -u UNITS, --units=UNITS
                        display storage size in given units
  -o OUTPUT_MODE, --output-mode=OUTPUT_MODE
                        Output mode, only json is supported currently. Default
                        is to print to console.
root@master-node:~#
```
      
Listing Volumes
---------------

By default gstatus prints an overview of all the volumes available in the
cluster. However, user can filter the volumes by specifying -v <volname>, more
than one volume can be specified by repeated invocation of -v. Or a regular
expression can be provided with -v option. For example:

gstatus -v '.*perf'

Ensure to use single quotes around the pattern, else shell file globbing will
include unnecessary input. The above pattern fetches all the volumes whose name
ends with perf. Any standard regular expression can be provided.

User can request more detailed volume information by providing the -a
option. Other volume options include -b, -q, -s which provides brick, quota, and
snapshot details respectively.

Quota
-----

By default gstatus reports `Quota: on' if quota is set. With options -a or -q
the list of all quota entries, size, and usage is reported.


Understanding the output
========================

gstatus output is made up of two parts:

a. Cluster infromation.
b. Volume information.

(There will be more as we add self-heal, rebalance, geo-replication ...)

a. Cluster information

Cluster information provides the health of the cluster and reports the number of
nodes reachable, the number of volumes in the cluster and the number of volumes
which are up.

b. Volume Information

There are three columns in the volume section namely volume name, volume type
(Replicate, Distribute, Distributed-Disperse, Disperse), and additional volume
related information. The third column provides wealth of volume information
which includes:

1. Status - (Started/Stopped)
2. Health (Displayed only when volume is started):
          i) UP       - All bricks are up and volume is healthy.
         ii) DOWN     - All bricks are down (needs immediate attention).
        iii) PARTIAL  - Only some of the bricks are up. (volume is functional).
         iv) DEGRADED - Some of the sub-volumes are down. (In case of distribute
                        data might not be accessible)
3. Capacity  - Volume capacity. Displayed units can be controlled by -u switch.
4. Snapshots - By default only snapshot count is shown. Detailed information can
               be viewed by using -s or -a switch to gstatus.
5. Bricks    - Brick list is not shown by default. Can be viewed by using -b or -a
               switch.
6. Quota     - List of directories on which quota is set can be viewed by
               running gstatus with -q or -a switch. By default just the quota
               status is shown which is on/off.

Output formats
==============
By default output is displayed on screen in a pretty printed format.
Alternatively, user can generate JSON output by passing -o json to gstatus
command.

