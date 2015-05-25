from gstatus.libutils.utils import display_bytes


class Brick(object):
    """ Brick object populated initially through vol info, and then updated
        with data from a vol status <bla> detail command """

    num_bricks = 0

    def __init__(self, brick_path, node_instance, volume_name):
        self.brick_path = brick_path
        self.node = node_instance
        self.node_name = brick_path.split(':')[0]
        self.up = False
        self.mount_options = {}
        self.fs_type = ''
        self.device = ''
        self.device_type = ''  # LVM, partition
        self.size = 0
        self.free = 0
        self.used = 0
        self.heal_count = 0
        self.owning_volume = volume_name
        # self.self_heal_enabled = False # default to off

        Brick.num_bricks += 1

    @classmethod
    def brick_count(cls):
        return Brick.num_bricks

    def update(self, state, size, free, fsname, device, mnt_options):
        """ apply attributes to this brick """

        self.up = state
        self.size = size  # KB to convert to GB
        self.free = free
        self.used = size - free
        self.fs_type = fsname
        self.device = device
        if 'mapper' in device:
            self.device_type = 'LVM'

        # convert the mount options to a dict, for easy query later
        mnt_parms = mnt_options.split(',')
        for opt in mnt_parms:
            if '=' in opt:
                (key, value) = opt.split('=')
                self.mount_options[key] = value
            else:

                self.mount_options[opt] = True

    @property
    def print_brick(self):
        """ provide an overview of this brick for display 
        :rtype : returns hum readable brick layout for the console display
        """

        state = "UP" if self.up else "DOWN"

        if self.heal_count > 0:
            heal_string = "S/H Backlog %d" % self.heal_count
        else:
            heal_string = ""

        fmtd = ("%s(%s) %s/%s %s"
                % (self.brick_path, state,
                   display_bytes(self.used),
                   display_bytes(self.size),
                   heal_string))

        return fmtd
