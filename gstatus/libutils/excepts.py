
class GlusterEmptyPool(Exception):
    pass

class GlusterNoPeerStatus(Exception):
    pass

class GlusterFailedBrick(Exception):
    pass

class GlusterFailedVolume(Exception):
    pass

class GlusterNotPeerNode(Exception):
    pass

class GlusterAnotherTransaction(Exception):
    pass
