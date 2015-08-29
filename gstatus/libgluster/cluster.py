

from glob import glob
import sys
import os
import xml.etree.ElementTree as ETree
from xml.parsers.expat import ExpatError
import gstatus.gstatuscfg.config as cfg
import json

from gstatus.libgluster.node import Node
from gstatus.libgluster.volume import Volume
from gstatus.libgluster.brick import Brick
from gstatus.libgluster.snapshot import Snapshot
from gstatus.libcommand.glustercmd import set_active_peer, GlusterCommand
from gstatus.libutils.utils import version_ok, get_attr
from gstatus.libutils.network import is_ip, host_aliases, get_ipv4_addr


class Cluster(object):
    """ The cluster object is the parent of nodes, bricks and volumes """

    # definition of the cluster attributes that should be used when
    # displaying the cluster in json/keyvalue format
    attr_list = ['status', 'glfs_version', 'node_count', 'nodes_active',
                 'volume_count', 'brick_count', 'bricks_active', 'volume_summary',
                 'sh_enabled', 'sh_active', 'raw_capacity', 'usable_capacity',
                 'client_count', 'used_capacity', 'product_name', 'over_commit',
                 'snapshot_count']

    def __init__(self):

        # counters
        self.node_count = 0
        self.volume_count = 0
        self.brick_count = 0
        self.snapshot_count = 0
        self.snapshot_capable = False

        self.sh_enabled = 0  # sh = self heal

        self.nodes_active = 0
        self.bricks_active = 0
        self.sh_active = 0

        self.node = {}  # dict of node objects indexed uuid

        self.nodes_down = 0

        self.volume = {}
        self.brick = {}

        self.glfs_version = ''

        self.raw_capacity = 0
        self.usable_capacity = 0
        self.used_capacity = 0
        self.over_commit = 'No'

        self.messages = []  # cluster error messages

        self.has_volumes = False
        self.status = "healthy"  # be optimistic at first :)

        self.volume_summary = {'up': 0, 'degraded': 0, 'partial': 0, 'down': 0}

        self.output_mode = ''  # console, json, keyvalue based output

        self.num_clients = 0
        self.client_set = set()
        self.num_connections = 0

        self.product_name = ''  # Product identifier, RHS release info or
        self.product_shortname = ''  # Community

        self.get_version()
        self.nodes_down = 0

        self.ip_list = []  # list of IP's from all nodes

    def initialise(self):
        """ call the node, volume 'generator' to create the child objects
            (bricks are created within the volume logic) """

        self.has_volumes = True if glob('/var/lib/glusterd/vols/*/trusted-*-fuse.vol') else False

        set_active_peer()  # setup GlusterCommand class to have a valid node for commands

        # if has_volumes is populated we have vol files, then it's ok to
        # run the queries to define the node and volume objects
        if self.has_volumes:

            self.define_nodes()

            self.define_volumes()

            # if this cluster supports snapshots, take a look to see if
            # there are any

            self.snapshot_capable = version_ok(self.glfs_version, cfg.snapshot_support)

            if self.snapshot_capable:
                self.define_snapshots()

                self.snapshot_count = Snapshot.snap_count()

        else:
            # no volumes in this cluster, print a message and abort
            print "This cluster doesn't have any volumes/daemons running."
            print "The output below shows the current nodes attached to this host.\n"

            cmd = GlusterCommand('gluster pool list')
            cmd.run()
            for line in cmd.stdout:
                print line
            print
            exit(12)

    def get_node(self, node_string):
        """
        receive an IP or name of a node and return the corresponding uuid
        """
        node_uuid = ''

        for uuid in self.node:
            node = self.node[uuid]
            if node_string in node.alias_list:
                node_uuid = uuid
                break

        return node_uuid

    def define_nodes(self):

        """ define the node objects for this cluster based on gluster pool list output """

        if self.output_mode == 'console' and not cfg.no_progress_msgs:
            # display a progress message
            sys.stdout.write("Processing nodes" + " " * 20 + "\n\r\x1b[A")

        cmd = GlusterCommand('gluster pool list --xml')
        cmd.run()

        if cmd.rc != 0:
            print "glusterd did not respond to a peer status request, gstatus"
            print "can not continue.\n"
            exit(12)

            # define a list of elements in the xml that we're interested in
        field_list = ['hostname', 'uuid', 'connected']

        xml_string = ''.join(cmd.stdout)
        xml_root = ETree.fromstring(xml_string)

        peer_list = xml_root.findall('.//peer')

        for peer in peer_list:
            node_info = get_attr(peer, field_list)
            this_hostname = node_info['hostname']
            alias_list = []

            if this_hostname == 'localhost':
                # output may say localhost, but it could be a reponse from a
                # foreign peer, since the local glusterd could be down
                if GlusterCommand.targetNode == 'localhost':
                    local_ip_list = get_ipv4_addr()  # Grab all IP's
                    for ip in local_ip_list:
                        alias_list += host_aliases(ip)
                    alias_list.append('localhost')
                else:
                    this_hostname = GlusterCommand.targetNode
                    alias_list = host_aliases(this_hostname)
                    alias_list.append('localhost')
            else:
                alias_list = host_aliases(this_hostname)

            # DEBUG ------------------------------------------------------------
            if cfg.debug:
                # Clean up all the empty strings in the list
                self.alias_stripped = [ele for ele in alias_list if ele != '']

                print "Creating a node object with uuid %s, with names of %s"%\
                    (node_info['uuid'], self.alias_stripped)
            # ------------------------------------------------------------------

            new_node = Node(node_info['uuid'], node_info['connected'],
                            alias_list)

            self.ip_list += [ip for ip in alias_list if is_ip(ip)]

            # add this node object to the cluster objects 'dict'
            self.node[node_info['uuid']] = new_node

        self.node_count = Node.node_count()

    def define_volumes(self):
        """ Create the volume + brick objects """

        if self.output_mode == 'console' and not cfg.no_progress_msgs:
            # print a progress message
            sys.stdout.write("Building volume objects" + " " * 20 + "\n\r\x1b[A")

        cmd = GlusterCommand("gluster vol info --xml")
        cmd.run()
        # (rc, vol_info) = issueCMD("gluster vol info --xml")

        xml_string = ''.join(cmd.stdout)
        xml_root = ETree.fromstring(xml_string)

        vol_elements = xml_root.findall('.//volume')

        for vol_object in vol_elements:

            # set up a dict for the initial definition of the volume
            vol_dict = {}

            # build a dict for the initial volume settings. An attribute error results in a default
            # value being assigned (e.g. on older glusterfs disperse related fields are missing)
            for attr in Volume.volume_attr:
                try:
                    vol_dict[attr] = vol_object.find('./' + attr).text
                except AttributeError:
                    vol_dict[attr] = '0'

            # create a volume object, for this volume
            new_volume = Volume(vol_dict)
            self.volume[new_volume.name] = new_volume

            if cfg.debug:
                print "defineVolumes. Adding volume %s" % new_volume.name

            # add information about any volume options
            opt_nodes = vol_object.findall('.//option')
            for option in opt_nodes:
                for n in option.getchildren():
                    if n.tag == 'name':
                        key = n.text
                    elif n.tag == 'value':
                        value = n.text
                        new_volume.options[key] = value

                        # Protocols are enabled by default, so we look
                        # for the volume tuning options that turn them
                        # off
                        if key == 'user.cifs':
                            if value in ['disable', 'off', 'false']:
                                new_volume.protocol['SMB'] = 'off'

                        elif key == 'nfs.disable':
                            if value in ['on', 'true']:
                                new_volume.protocol['NFS'] = 'off'

            # get bricks listed against this volume, and create the Brick object(s)
            brick_nodes = vol_object.findall('.//brick')

            # list holding brick paths
            repl = []
            ctr = 1

            for brick in brick_nodes:

                brick_path = brick.text
                new_volume.brick_order.append(brick_path)
                (hostname, pathname) = brick_path.split(':')

                if cfg.debug:
                    print "defineVolumes. Adding brick %s to %s" % (brick_path,
                                                                    new_volume.name)

                node_uuid = self.get_node(hostname)

                # add this bricks owning node to the volume's attributes
                try:
                    new_volume.node[node_uuid] = self.node[node_uuid]

                except KeyError:
                    print "Unable to associate brick %s with a peer in the cluster, possibly due" % brick_path
                    print "to name lookup failures. If the nodes are not registered (fwd & rev)"
                    print "to dns, add local entries for your cluster nodes in the the /etc/hosts file"
                    sys.exit(16)

                new_brick = Brick(brick_path, self.node[node_uuid], new_volume.name)

                # Add the brick to the cluster and volume
                self.brick[brick_path] = new_brick
                new_volume.brick[brick_path] = new_brick

                # add this brick to the owning node
                brick_owner = self.node[node_uuid]
                brick_owner.brick[brick_path] = new_brick

                if (new_volume.replicaCount > 1) or (new_volume.disperseCount > 0):
                    repl.append(brick_path)
                    bricks_per_subvolume = max(new_volume.replicaCount, new_volume.disperseCount)
                    ctr += 1
                    if ctr > bricks_per_subvolume:
                        ctr = 1

                        # add this replica set to the volume's info
                        new_volume.subvolumes.append(repl)
                        # drop all elements from temporary list
                        repl = []

            # By default from gluster 3.3 onwards, self heal is enabled for
            # all replicated/disperse volumes. We look at the volume type, and if it
            # is replicated and hasn't had self-heal explicitly disabled the
            # self heal state is inferred against the nodes that contain the
            # bricks for the volume. With this state in place, the updateState
            # method can cross-check to see what is actually happening

            if ('replicate' in new_volume.typeStr.lower()) or ('disperse' in new_volume.typeStr.lower()):

                heal_enabled = True  # assume it's on

                if 'cluster.self-heal-daemon' in new_volume.options:
                    if new_volume.options['cluster.self-heal-daemon'].lower() in ['off', 'false']:
                        heal_enabled = False

                new_volume.self_heal_enabled = heal_enabled

                if heal_enabled:

                    node_set = set()  # use a set to maintain a unique group of nodes

                    for brick_path in new_volume.brick:
                        this_brick = self.brick[brick_path]
                        this_node = this_brick.node
                        node_set.add(this_node)
                        this_node.self_heal_enabled = True

                    self.sh_enabled = len(node_set)

        self.volume_count = Volume.volume_count()
        self.brick_count = Brick.brick_count()

    def define_snapshots(self):
        """
        Process each of the discovered volumes to look for any
        associated snapshots
        """

        # process each discovered volume
        for volume_name in self.volume:

            this_volume = self.volume[volume_name]

            cmd = GlusterCommand("gluster snap list %s" % volume_name)
            cmd.run()
            # (rc, snap_info) = issueCMD("gluster snap list %s"%(volume_name))

            if cmd.rc == 0:
                # process the snap information
                if not cmd.stdout[0].lower().startswith('no snapshots'):



                    for snap in cmd.stdout:
                        snap_name = snap.strip()

                        if cfg.debug:
                            print "defineSnapshots. Creating a snapshot instance for volume '%s' called '%s'" % (volume_name, snap_name)

                        new_snapshot = Snapshot(snap_name, this_volume, volume_name)
                        this_volume.snapshot_list.append(new_snapshot)

                    this_volume.snapshot_count = len(this_volume.snapshot_list)

            if cfg.debug:
                print "defineSnapshots. Volume '%s' has %d snapshots" % (volume_name, this_volume.snapshot_count)

    def get_version(self):
        """ Sets the current version and product identifier for this cluster """
        cmd = GlusterCommand("gluster --version")
        # (rc, versInfo) = issueCMD("gluster --version")
        cmd.run()

        self.glfs_version = cmd.stdout[0].split()[1]

        if os.path.exists('/etc/redhat-storage-release'):
            with open('/etc/redhat-storage-release', 'r') as RHS_version:
                # example contents - Red Hat Storage Server 3.0
                self.product_name = RHS_version.readline().rstrip()
                lc_name = self.product_name.replace('update', '.')
                self.product_shortname = "RHGS Server v%s" %\
                    (''.join(lc_name.split()[5:]))
        else:
            self.product_name = self.product_shortname = "Community"

    def active_nodes(self):
        """ Count no. of nodes in an up state """

        for uuid in self.node:
            if self.node[uuid].state == '1':
                self.nodes_active += 1

        return self.nodes_active

    def active_bricks(self):
        """ return the number of bricks in an up state """

        for brick_name in self.brick:
            if self.brick[brick_name].up:
                self.bricks_active += 1

        return self.bricks_active

    def health_checks(self):
        """ perform checks on elements that affect the reported state of the cluster """

        # The idea here is to perform the most significant checks first
        # so the message list appears in a priority order

        # 1. Check the volumes
        for volume_name in self.volume:
            this_volume = self.volume[volume_name]

            if 'down' in this_volume.volume_state:
                self.messages.append("Volume '%s' is down" % volume_name)
                self.status = 'unhealthy'

            if 'partial' in this_volume.volume_state:
                self.messages.append(
                    "Volume '%s' is in a PARTIAL state, some data is inaccessible data, due to missing bricks"
                    % volume_name)
                self.messages.append("WARNING -> Write requests may fail against volume '%s'" % this_volume.name)
                self.status = 'unhealthy'

                # 2. Check for conditions detected at the node level
        for uuid in self.node:
            this_node = self.node[uuid]
            if this_node.state != '1':
                # https://bugzilla.redhat.com/show_bug.cgi?id=1254514,
                # node_name comes as empty
                # self.messages.append("Cluster node '%s' is down" %
                # (this_node.node_name()))
                self.nodes_down += 1
                self.status = 'unhealthy'

            if this_node.self_heal_enabled != this_node.self_heal_active:
                # https://bugzilla.redhat.com/show_bug.cgi?id=1254514,
                # decided to remove the self-heal status as it is
                # redunant information
                # self.messages.append("Self heal daemon is down on %s" % (this_node.node_name()))
                self.status = 'unhealthy'

        # Print the number of nodes that are down
        if self.nodes_down == 1:
            self.messages.append("One of the nodes in the cluster is down")
        elif self.nodes_down > 1:
            self.messages.append("%s nodes in the cluster are down"%self.nodes_down)

        # 3. Check the bricks
        for brick_name in self.brick:

            this_brick = self.brick[brick_name]

            # 3.1 check for state
            if not this_brick.up:
                self.messages.append(
                    "Brick %s in volume '%s' is down/unavailable" % (brick_name, this_brick.owning_volume))

                # 3.2 check for best practice goes here (minor error messages - FUTURE)

        if self.bricks_active < Brick.brick_count():
            self.messages.append("INFO -> Not all bricks are online, so capacity provided is NOT accurate")

            # 4. Insert your checks HERE!

    def check_self_heal(self):
        """ return the number of nodes that have self-heal active """

        for uuid in self.node:
            if self.node[uuid].self_heal_active:
                self.sh_active += 1

        return self.sh_active

    def num_self_heal(self):
        """ return the number of nodes with self heal enabled """

        for uuid in self.node:
            if self.node[uuid].self_heal_enabled:
                self.sh_enabled += 1

        return self.sh_enabled

    def update_state(self, self_heal_backlog):
        """ update the state of the cluster by processing the output of 'vol status' commands

            - vol status all detail --> provides the brick info (up/down, type), plus volume capacity
            - vol status all --> self heal states

        """
        if self.output_mode == 'console' and not cfg.no_progress_msgs:
            # print a progress message
            sys.stdout.write("Updating volume information" + " " * 20 + "\n\r\x1b[A")

        # WORKAROUND
        # The code issues n vol status requests because issueing a vol status
        # wih the 'all' parameter can give bad xml when nodes are not
        # present in the cluster. By stepping through each volume, the
        # xml, while still buggy can be worked around
        # Process all volumes known to the cluster
        for volume_name in self.volume:

            # 'status' is set from a vol info command. This will show whether the
            # vol is created (0), started (1), or stopped (2). We're only interested
            # in the started state, when issuing the vol status command
            if self.volume[volume_name].status == 1:

                cmd = GlusterCommand("gluster vol status %s detail --xml" % volume_name)
                # (rc, vol_status) = issueCMD("gluster vol status %s detail --xml"%(volume_name))
                cmd.run()

                # Need to check opRet element since for xml based gluster commands
                # do NOT pass a return code back to the shell!
                # gluster_rc = int([line.replace('<',' ').replace('>',' ').split()[1]
                #               for line in vol_status if 'opRet' in line][0])

                if cmd.rc == 0:
                    xml_string = ''.join(cmd.stdout)
                    xml_obj = ETree.fromstring(xml_string)

                    # Update the volume, to provide capacity and status information
                    self.volume[volume_name].update(xml_obj)

                else:
                    # Being unable to get a vol status for a known volume
                    # may indicate a peer transitioning to disconnected state
                    # so issue an error message and abort the script
                    print "\n--> gstatus has been unable to query volume '" + volume_name + "'"
                    print "\nPossible cause: cluster is currently reconverging after a node"
                    print "has entered a disconnected state."
                    print "\nResponse: Rerun gstatus or issue a peer status command to confirm\n"
                    exit(16)

                # -----------------------------------------------------------------------------
                # Issue a vol status then use the output to look for active tasks and self heal
                # state information
                # -----------------------------------------------------------------------------
                cmd = GlusterCommand("gluster vol status %s --xml" % volume_name)
                cmd.run()

                # (rc, vol_status) = issueCMD("gluster vol status %s --xml"%(volume_name))
                # gluster_rc = int([line.replace('<',' ').replace('>',' ').split()[1]
                #           for line in vol_status if 'opRet' in line][0])
                xml_string = ''.join(cmd.stdout)
                xml_root = ETree.fromstring(xml_string)

                task_elements = xml_root.findall('.//task')

                for task in task_elements:
                    task_name = task.find('./type').text
                    task_status = task.find('./status').text
                    task.status_str = task.find('./statusStr').text
                    if task_status == '1':
                        self.volume[volume_name].task_list.append(task_name)

                # ---------------------------------------------------------------------
                # If the volume has self_heal enabled, we look at the state of the daemons
                # ---------------------------------------------------------------------
                if self.volume[volume_name].self_heal_enabled:

                    if self.output_mode == 'console' and not cfg.no_progress_msgs:
                        sys.stdout.write("Analysing Self Heal daemons on %s %s\n\r\x1b[A" % (volume_name, " " * 20))

                    if cmd.rc == 0:

                        # self_heal_list = []

                        node_elements = xml_root.findall('.//node')
                        # print "DEBUG --> node elements in vol status is " + str(len(node_elements))

                        # first get a list of self-heal elements from the xml
                        for node in node_elements:

                            # WORKAROUND
                            # there's a bug in some versions of 3.4, where when a node is missing
                            # the xml returned is malformed returning a node
                            # within a node so we need to check the subelements
                            # to see if they're valid.
                            if node.find('./node'):
                                continue

                            if node.find('./hostname').text == 'Self-heal Daemon':
                                node_name = node.find('./path').text
                                node_state = node.find('./status').text
                                # uuid = ''

                                # convert the name to a usable uuid
                                if node_name == 'localhost':
                                    uuid = self.get_node(GlusterCommand.targetNode)
                                else:
                                    uuid = self.get_node(node_name)

                                if not uuid:
                                    # tried to resolve the name but couldn't
                                    print ("Cluster.updateState : Attempting to use a 'path' (%s) for "
                                           "a self heal daemon that" % node_name)
                                    print "does not correspond to a peer node, and can not continue\n"
                                    exit(16)

                                if self.node[uuid].self_heal_enabled:

                                    if node_state == '1':
                                        self.node[uuid].self_heal_active = True
                                    else:
                                        self.node[uuid].self_heal_active = False

                    # update the self heal flags, based on the vol status
                    self.volume[volume_name].set_self_heal_stats()  # high level info

                    if self_heal_backlog:
                        # now get low level info to check for heal backlog
                        self.volume[volume_name].update_self_heal(self.output_mode)

                        if 'UNAVAILABLE' in self.volume[volume_name].self_heal_string:
                            # add message to cluster messages
                            self.messages.append(
                                'WARNING -> self heal query did not complete for %s. Debug with -D or use '
                                '-t to increase cmd timeout' % volume_name)

            this_state = self.volume[volume_name].volume_state

            if this_state == 'up':
                self.volume_summary['up'] += 1
            elif 'degraded' in this_state:
                self.volume_summary['degraded'] += 1
            elif 'partial' in this_state:
                self.volume_summary['partial'] += 1
            else:
                self.volume_summary['down'] += 1

        self.active_nodes()  # update active node counter
        self.active_bricks()  # update active brick counter
        self.check_self_heal()

        self.calc_connections()

    def calc_capacity(self):
        """ update the cluster's overall capacity stats based on the
            brick information """

        # calculate the raw and used from the bricks
        brick_devs = []
        for brick_path in self.brick:
            this_brick = self.brick[brick_path]

            node = this_brick.node_name
            device_path = node + ":" + this_brick.device

            if device_path in brick_devs:
                self.over_commit = 'Yes'
                continue

            brick_devs.append(device_path)
            self.raw_capacity += this_brick.size
            self.used_capacity += this_brick.used

        # derive the clusters usable space from the volume definition(s)
        for vol_name in self.volume:
            this_volume = self.volume[vol_name]
            self.usable_capacity += this_volume.usable_capacity

    def __str__(self):
        """ return a human readable form of the cluster object for processing
            by logstash, splunk etc """

        data = {}
        data_string = ''

        for key, value in sorted(vars(self).iteritems()):

            if key in Cluster.attr_list:

                if self.output_mode == 'json':
                    data[key] = value

                elif self.output_mode == 'keyvalue':
                    if isinstance(value, dict):
                        for dict_key in value:
                            item_value = value[dict_key] if isinstance(value[dict_key], int) else "'%s'" % (
                                value[dict_key])
                            data_string += "%s_%s=%s," % (key, dict_key, item_value)

                    else:
                        item_value = value if isinstance(value, int) else "'%s'" % value
                        data_string += "%s=%s," % (key, item_value)

        if self.output_mode == 'json':
            summary_list = []
            for vol_name in self.volume:
                this_volume = self.volume[vol_name]
                summary_list.append(this_volume.volume_summary)
            data['volume_summary'] = summary_list
            data_string = json.dumps(data, sort_keys=True)

        elif self.output_mode == 'keyvalue':
            data_string = data_string[:-1]

        return data_string

    def calc_connections(self):
        """ Issue a vol status all clients --xml and invoke the volume's
            clientCount method to determine unique clients connected to
            the clusters volume(s) """

        if self.output_mode == 'console' and not cfg.no_progress_msgs:
            # print a progress message
            sys.stdout.write("Processing gluster client connections" + " " * 20 + "\n\r\x1b[A")

        cmd = GlusterCommand("gluster vol status all clients --xml")
        cmd.run()

        # (rc, vol_clients) = issueCMD("gluster vol status all clients --xml")

        # gluster_rc = int([line.replace('<',' ').replace('>',' ').split()[1]
        #               for line in vol_clients if 'opRet' in line][0]) if rc == 0 else rc

        if cmd.rc > 0:
            # unable to get the client connectivity information
            if self.output_mode == 'console' and not cfg.no_progress_msgs:
                print "\ngstatus has been unable to get the output of a 'vol status all clients --xml' command"
                print "and can not continue.\n"
            return

        # At this point the command worked, so we can process the results
        xml_string = ''.join(cmd.stdout)
        try:
            xml_root = ETree.fromstring(xml_string)
        except ExpatError:
            print "Malformed xml, try again later."

        volumes = xml_root.findall('.//volume')

        for volume_xml in volumes:
            # Find the volume name
            vol_name = volume_xml.find('./volName').text

            # process the volume xml
            self.volume[vol_name].client_count(volume_xml)

            # add the volumes unique set of clients to the clusters set
            self.client_set.update(self.volume[vol_name].client_set)
            self.num_connections += self.volume[vol_name].num_connections

        self.num_clients = len(self.client_set)
