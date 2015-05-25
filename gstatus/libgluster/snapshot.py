

class Snapshot(object):
    num_snapshots = 0

    def __init__(self, snap_name, parent_volume, volume_name):
        self.name = snap_name
        self.parent_object = parent_volume
        self.volume_name = volume_name
        self.created = None
        self.status = None

        Snapshot.num_snapshots += 1

    @classmethod
    def snap_count(cls):
        return Snapshot.num_snapshots
