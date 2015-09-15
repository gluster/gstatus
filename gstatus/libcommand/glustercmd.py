#!/usr/bin/env python
#
import os
import signal
#
import socket
import glob
import subprocess
import threading
#
import xml.etree.ElementTree as ETree
import gstatus.gstatuscfg.config as cfg


def set_active_peer():
    """ Supplemental function to set the target node for the GlusterCommand
        instances """

    def __glusterd_address():
        """ function to set the local address of glusterd - either localhost (default) or the bind address """
        bind_parm = "transport.socket.bind-address"
        local_glusterd = 'localhost'

        # assume the glusterd.vol file exists and this is a gluster node
        with open('/etc/glusterfs/glusterd.vol') as config_file:
            config = config_file.readlines()

        if config:
            for cfg_item in config:
                if not cfg_item.startswith("#") and bind_parm in cfg_item:
                    local_glusterd = cfg_item.rstrip().split(' ')[-1]
                    break

        return local_glusterd

    def __port_open(host_name='localhost'):
        port_number = 24007
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        return True if s.connect_ex((host_name, port_number)) == 0 else False

    glusterd_peers = "/var/lib/glusterd/peers/*"

    listening_peer = ''
    # we first look at glusterd on the local machine
    if __port_open(__glusterd_address()):
        listening_peer = 'localhost'
    else:
        # Get a list of peers
        try:

            for peerFile in glob.glob(glusterd_peers):
                with open(peerFile) as peer:
                    for option in peer:
                        if option.startswith('hostname'):
                            key, host_name = option.split('=')
                            host_name = host_name.strip()

                            if __port_open(host_name):
                                raise StopIteration

        except StopIteration:
            listening_peer = host_name

    GlusterCommand.targetNode = listening_peer


class GlusterCommand(object):
    targetNode = 'localhost'  # default to local machine

    def __init__(self, cmd, timeout=1):
        self.cmd = cmd
        self.cmdProcess = None
        self.timeout = timeout
        self.rc = 0  # -1 ... timeout
        # 0 .... successful
        # n .... RC from command

        self.stdout = []
        self.stderr = []

    def run(self):
        """ Run the command inside a thread to enable a timeout to be
            assigned """

        def command_thread():
            """ invoke subprocess to run the command """

            if GlusterCommand.targetNode is not "localhost":
                self.cmd += " --remote-host=%s" % GlusterCommand.targetNode

            self.cmdProcess = subprocess.Popen(self.cmd,
                                               shell=True,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE,
                                               preexec_fn=os.setsid)

            stdout, stderr = self.cmdProcess.communicate()
            self.stdout = stdout.split('\n')[:-1]
            self.stderr = stderr.split('\n')[:-1]

        thread = threading.Thread(target=command_thread)
        thread.start()

        thread.join(self.timeout)

        if thread.is_alive():
            if cfg.debug:
                print ('Gluster_Command. Response from glusterd has exceeded %d secs timeout, terminating the request'
                       % cfg.CMD_TIMEOUT)
            os.killpg(self.cmdProcess.pid, signal.SIGTERM)
            self.rc = -1

        else:
            # the thread completed normally
            if '--xml' in self.cmd:
                # set the rc based on the xml return code
                xmldoc = ETree.fromstring(''.join(self.stdout))
                self.rc = int(xmldoc.find('.//opRet').text)
            else:
                # set the rc based on the shell return code
                self.rc = self.cmdProcess.returncode
