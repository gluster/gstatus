class Node(object):
    """ Node object, just used as a container as a parent for bricks """

    num_nodes = 0

    node_state = {'0': 'down', '1': 'up'}

    def __init__(self, uuid, state, aliases):
        # self.node_name = node
        self.uuid = uuid
        self.state = state  # index for node_state dict
        # self.state_text = Node.node_state[state]
        self.brick = {}
        self.daemon_state = {}
        self.local = False  # is this the localhost?
        self.self_heal_enabled = False
        self.self_heal_active = False
        self.alias_list = aliases  # list of names this node is known by

        Node.num_nodes += 1

    @classmethod
    def node_count(cls):
        return Node.num_nodes

    def node_name(self):
        """
        Return a shortname or IP for this node
        """
        # if there is only one non-empty element, return that as the node name
        # otherwise, try and return the shortname
        if len(filter(None, self.alias_list)) == 1:
            # return the first non empty element
            return ''.join(filter(None, self.alias_list))
        else:
            # pass back the shortname - normally element 1
            return self.alias_list[1] if self.alias_list[1] != '' else self.alias_list[0]

