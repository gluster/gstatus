

import sys
import gstatus.gstatuscfg.config as cfg

from gstatus.libcommand.glustercmd import GlusterCommand


class Volume(object):
    """ Volume object, linking out to the bricks, and holding the description
        of the volume's attributes
    """

    num_volumes = 0

    # Volume states are -
    #   up      ... all bricks online, operational
    #   up(partial) ... one or more bricks offline, but replica in place
    #   up(degraded) ... at least one replica set is offline
    #   down        ... volume is down/stopped

    volume_states = ['unknown', 'up', 'down', 'up(partial)', 'up(degraded)']

    # declare the attributes that we're interested in from the vol info output
    volume_attr = ['name', 'status', 'statusStr', 'type', 'typeStr', 'replicaCount', 'disperseCount', 'redundancyCount']

    # status - 0=created, 1=started, 2 = stopped
    #
    # type - 4 = disperse, 5 = dist-repl

    def __init__(self, attr_dict):
        """ caller provides a dict, with the keys in the volume_attr list
            which we then apply when a volume is instantiated """

        # volume attribute names match those in the xml output
        for key, value in attr_dict.items():
            value = int(value) if value.isdigit() else value
            setattr(self, key, value)

        self.volume_state = 'down'  # start with a down state
        self.brick = {}  # pointers to the brick objects that make up this vol
        self.brick_order = []  # list of the bricks in the order they appear
        self.brick_total = 0
        self.subvolumes = []  # list, where each item is a tuple, of brick objects
        self.subvolume_state = []  # list show number of bricks offline in each repl set
        self.status_string = ''

        self.volume_summary = dict()  # high level description of the volume, used in
        # json output

        self.node = {}  # dict indexed by uuid pointing to node's within this volume

        self.options = {}
        self.raw_capacity = 0
        self.raw_used = 0
        self.usable_capacity = 0
        self.used_capacity = 0
        self.pct_used = 0
        self.nfs_enabled = True
        self.self_heal_enabled = False
        self.self_heal_string = 'N/A'
        self.self_heal_active = False  # default to not active
        self.self_heal_count = 0  # no. files being tracked for self heal

        # By default all these protocols are enabled by gluster
        self.protocol = {'SMB': 'on', 'NFS': 'on', 'NATIVE': 'on'}

        self.num_clients = 0
        self.num_connections = 0
        self.client_set = set()

        self.snapshot_count = 0
        self.snapshot_list = []  # list of snapshot objects
        self.max_snapshots = 256
        self.task_list = []  # list of active tasks running against this volume

        Volume.num_volumes += 1

    @classmethod
    def volume_count(cls):
        return Volume.num_volumes

    def brick_update(self, brick_xml):
        """ method to update a volume's brick"""

        node_info = {}
        for brick_info in brick_xml.getchildren():
            # print "DEBUG setting " + brick_info.tag + " to " + brick_info.text
            node_info[brick_info.tag] = brick_info.text

        brick_path = node_info['hostname'] + ":" + node_info['path']
        brick_state = True if node_info['status'] == '1' else False
        this_brick = self.brick[brick_path]

        # update this brick
        this_brick.update(brick_state,
                          int(node_info['sizeTotal']),
                          int(node_info['sizeFree']),
                          node_info['fsName'],
                          node_info['device'],
                          node_info['mntOptions'])

        # Add this bricks capacity info to the volume's stats
        self.raw_capacity += int(node_info['sizeTotal'])
        self.raw_used += int(node_info['sizeTotal']) - int(node_info['sizeFree'])

    def update(self, volume_xml):
        """ receive an xml document containing volume's attributes, process
            each element updating the volume info and associated
            brick information/state
        """

        if cfg.debug:
            print "Volume 'update'. Processing volume %s" % self.name

        node_elements = volume_xml.findall('.//node')
        # print "DEBUG --> this volume xml has %d node elements"%(len(node_elements))

        for node in node_elements:
            sub_element_count = len(node.getchildren())

            # for a good node definition, there are child elements but the
            # number of elements varies by gluster version
            # Version 3.4 ... 11 sub elements of <node>
            # Version 3.5 ... 12 sub elements of <node> 3.5 adds a 'peerid' child element
            if sub_element_count >= 11:
                # print "DEBUG --> Updating a brick"
                self.brick_update(node)
            else:
                # Skipping this node element since it doesn't have child elements
                # and is therefore malformed xml
                pass

        # ----------------------------------------------------------------
        # Brick info has been updated, we can calculate the volume capacity
        # but the volume needs to up at least partially up for the vol status
        # to return information.
        # ----------------------------------------------------------------

        (up_bricks, total_bricks) = self.brick_states()

        # if all the bricks are online the usable is simple
        if up_bricks == total_bricks:

            if self.disperseCount == 0:
                # this is a dist or repl volume type
                self.usable_capacity = self.raw_capacity / self.replicaCount
                self.used_capacity = self.raw_used / self.replicaCount

            else:
                # this is a disperse volume, with all bricks online
                # assumption : all bricks are the same size
                disperse_yield = float(self.disperseCount - self.redundancyCount) / self.disperseCount
                self.usable_capacity = self.raw_capacity * disperse_yield
                self.used_capacity = self.raw_used * disperse_yield

        else:

            # have to account for the available space in each subvolume
            # for the calculation
            if (self.replicaCount > 1) or (self.disperseCount > 0):
                for subvolume in self.subvolumes:
                    for brick_path in subvolume:
                        if self.brick[brick_path].up:
                            self.usable_capacity += self.brick[brick_path].size
                            self.used_capacity += self.brick[brick_path].used

                            # for replica volumes, only include one of the bricks in the calculations
                            if self.replicaCount > 1:
                                break
            else:
                self.usable_capacity = self.raw_capacity
                self.used_capacity = self.raw_used

        # with the volume used and usable calculated, we can derive the %used
        if self.usable_capacity > 0:
            self.pct_used = (self.used_capacity / float(self.usable_capacity)) * 100
        else:
            self.pct_used = 0

        # ----------------------------------------------------------------
        # Now look at the brick status and volume type to derive the volume
        # status
        # ----------------------------------------------------------------
        if up_bricks == 0:
            self.volume_state = 'down'
        else:
            self.volume_state = 'up'

            if (self.replicaCount > 1) or (self.disperseCount > 0):
                # this volume has inbuilt data protection, so check the status of the
                # bricks in each subvolume to determine overall volume health

                subvolume_states = []

                for subvolume in self.subvolumes:
                    state = 0  # initial state is 0 = all good, n > 0 = n bricks down

                    for brick_path in subvolume:
                        if not self.brick[brick_path].up:
                            state += 1
                    subvolume_states.append(state)

                self.subvolume_state = subvolume_states

                worst_subvolume = max(subvolume_states)

                # check if we have a problem (i.e. > 0)
                if worst_subvolume > 0:

                    subvolume_problem = max(self.replicaCount, (self.redundancyCount + 1))

                    if worst_subvolume == subvolume_problem:
                        # if this volume is only contains one subvolume, and the bricks down > redundancy level
                        # then the volume state needs to show down
                        if len(self.subvolumes) == 1:
                            self.volume_state = 'down'
                        else:
                            self.volume_state += "(partial)"
                    else:
                        self.volume_state += "(degraded)"

            else:

                # This volume is not 'protected', so any brick disruption leads
                # straight to a 'partial' availability state
                if up_bricks != total_bricks:
                    self.volume_state += '(partial) '

        self.volume_summary['volume_name'] = self.name
        self.volume_summary['state'] = self.volume_state
        self.volume_summary['usable_capacity'] = self.usable_capacity
        self.volume_summary['used_capacity'] = self.used_capacity
        self.volume_summary['snapshot_count'] = self.snapshot_count

    def num_bricks(self):
        """ return the number of bricks in the volume """

        return len(self.brick)

    def brick_states(self):
        """ return a tupe of online bricks and total bricks for this volume """

        all_bricks = len(self.brick)
        online_bricks = 0
        for brick_path in self.brick:
            if self.brick[brick_path].up:
                online_bricks += 1
        return (online_bricks, all_bricks)

    def update_self_heal(self, output_mode):
        """ Updates the state of self heal for this volume """

        # first check if this volume is a replicated or disperse volume, if not
        # set the state string to "not applicable"
        if ('replicate' not in self.typeStr.lower()) and ('disperse' not in self.typeStr.lower()):
            self.self_heal_string = 'N/A'
            return

        # if self-heal is disabled by option...
        if 'cluster.self-heal-daemon' in self.options:
            if self.options['cluster.self-heal-daemon'].lower() in ['off', 'false']:
                self.self_heal_string = 'DISABLED'
                return

        if output_mode == 'console' and not cfg.no_progress_msgs:
            sys.stdout.write("Analysing Self Heal backlog for %s %s \n\r\x1b[A" % (self.name, " " * 20))

        # On gluster 3.4 & 3.5 vol heal with --xml is not supported so parsing
        # has to be done the old fashioned way :(

        # The command is invoked with a timeout clause too
        cmd = GlusterCommand("gluster vol heal %s info" % self.name, timeout=cfg.CMD_TIMEOUT)
        cmd.run()
        # (rc, vol_heal_output) = issueCMD("gluster vol heal %s info"%(self.name))

        if cmd.rc == 0:

            total_heal_count = 0

            # in gluster 3.4 even though the cluster and bricks are defined with IP addresses
            # the vol heal can return an fqdn for the hostname - so we have to account for that

            for line in cmd.stdout:

                if line.lower().startswith('brick'):
                    (node, path_name) = line.replace(':', ' ').split()[1:]

                    if cfg.debug:
                        print "updateSelfHeal. self heal cmd gave a node name of %s" % node

                    # 3.4.0.59 added trailing '/' to brick path,so remove it!
                    brick_path = node + ":" + path_name.rstrip('/')

                heal_count = 0
                if line.lower().startswith('number') and line.split(':')[1] != ' -':
                    heal_count = int(line.split(':')[1])

                    try:

                        self.brick[brick_path].heal_count = heal_count
                        if cfg.debug:
                            print "updateSelfHeal. brick path from self heal matched brick object successfully"

                    except KeyError:

                        if cfg.debug:
                            print ("updateSelfHeal. brick path from self heal != any brick object, "
                                   "processing nodes to locate the brick")

                        # cycle though the nodes associated with this volume
                        match_found = False
                        for uuid in self.node:

                            # if this node does NOT match the node in the brickpath, skip it
                            if node not in self.node[uuid].alias_list:
                                continue

                            # now convert the brickpath to something usable
                            for alias in self.node[uuid].alias_list:
                                new_path = alias + ":" + path_name.rstrip('/')
                                if new_path in self.brick:
                                    brick_path = new_path
                                    match_found = True
                                    break

                            if match_found:
                                break

                        if cfg.debug:
                            print "updateSelfHeal. using brick path match of %s" % brick_path

                    total_heal_count += heal_count

            self.self_heal_count = total_heal_count
            if total_heal_count > 0:
                self.self_heal_string += "   Heal backlog of %d files" % total_heal_count
            else:
                self.self_heal_string += "   All files in sync"

        else:
            # vol heal command failed - just flag the problem
            if cfg.debug:
                print ("Volume updateSelfHeal. Query for self heal details timed out - "
                       "maybe run again with a larger -t value?")
            self.self_heal_string += " HEAL DATA UNAVAILABLE"

    def set_self_heal_stats(self):
        """ return a string active/enable self heal states for the
            nodes that support this volume """

        enabled = 0
        active = 0

        for brick_path in self.brick:
            this_brick = self.brick[brick_path]

            if this_brick.node.self_heal_enabled:
                enabled += 1
            if this_brick.node.self_heal_active:
                active += 1

        self.self_heal_string = "%2d/%2d" % (active, enabled)

    def print_layout(self):
        """ print function used to show the relationships of the bricks in
            a volume """

        vol_description = {'Replicate': ['Replica Set', 'afr'],
                           'Disperse': ['Disperse set', 'ida']
                           }
        vol_description['Distributed-Replicate'] = vol_description['Replicate']
        vol_description['Distributed-Disperse'] = vol_description['Disperse']

        supported_volume_types = ['Replicate', 'Distribute', 'Distributed-Replicate', 'Disperse', 'Distributed-Disperse']

        if self.typeStr not in supported_volume_types:
            print "\tDisplay of this volume type has yet to be implemented"
            return

        print "\t%s %s" % (self.name.ljust(16, '-'), '+')
        print "\t" + " " * 17 + "|"
        offset = 16

        if self.typeStr.startswith('Dist'):
            print " " * offset + "Distribute (dht)"
            offset = 25
        elif self.typeStr.startswith('Disp'):
            print " " * offset + "Disperse (ida)"
            offset = 25
        else:
            print " " * offset + "Replicated (afr)"
            offset = 25

        if (self.replicaCount == 1) and (self.disperseCount == 0):

            # Distributed layout
            for brick_name in self.brick_order:
                brick_info = self.brick[brick_name].print_brick
                print (" " * offset + "|\n" + " " * offset + "+--" + brick_info)

        else:

            # Replicated or dispersed volume
            subvol_id = 0
            subvol_type_text = vol_description[self.typeStr][0]
            subvol_xlator = vol_description[self.typeStr][1]
            num_subvols = len(self.subvolumes)
            link_char = "|"
            for subvol in self.subvolumes:

                if subvol_id == (num_subvols - 1):
                    link_char = " "

                print (" " * offset + "|\n" + " " * offset + "+-- %s" % subvol_type_text
                       + str(subvol_id) + " (%s)" % subvol_xlator)
                padding = " " * offset + link_char + "     "
                for brick_path in subvol:
                    brick_info = self.brick[brick_path].print_brick
                    print (padding + "|\n" + padding + "+--" + brick_info)
                subvol_id += 1
        print

    def client_count(self, vol_stat_clients_xml):
        """ receive volume xml, and parse to determine the total # of
            unique clients connected to the volume """

        # By default the xml provides a 'clientCount' child element for
        # the volume, but this number does not account for duplicate clients
        # connected e.g. One client can connect to a volume multiple times
        # getting counted 'n' times. This code determines unique clients
        # connected to the volume - since that would be more useful to
        # sysadmins/Operations

        brick_clients_list = vol_stat_clients_xml.findall('.//clientsStatus')

        # Since sets only store unique values, we'll use that to track
        # unique clients

        connection_count = 0

        for brick in brick_clients_list:
            clients = brick.findall('.//hostname')
            for client in clients:
                client_name, port_number = client.text.split(':')

                # ignore the connections from the gluster nodes themselves
                # that connect to the bricks.
                # if int(port_number) < 2048:
                #     continue

                # now we're left with connection information, so we count unique
                # IPs as hosts connections, but also provide all connections
                # for native client/libgfapi

                self.client_set.add(client_name)
                connection_count += 1

        self.num_clients = len(self.client_set)
        self.num_connections = connection_count
