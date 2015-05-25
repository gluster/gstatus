

def display_bytes(in_bytes, units='bin'):
    """
    Routine to convert a given number of bytes into a more human readable form

    - Based on code in Mark Pilgrim's Dive Into Python book

    Input  : number of bytes
    Output : returns a MB / GB / TB value for bytes

    """

    suffixes = {1000: ['KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'],
                1024: ['KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']}

    rounding = {'K': 0, 'M': 0, 'G': 0, 'T': 1, 'P': 2, 'Z': 2, 'Y': 2}

    size = float(in_bytes)

    if size < 0:
        raise ValueError('number must be non-negative')

    divisor = 1024 if units == 'bin' else 1000
    for suffix in suffixes[divisor]:
        size /= divisor
        if size < divisor:
            char1 = suffix[0]
            precision = rounding[char1]
            size = round(size, precision)

            return '{0:.2f} {1}'.format(size, suffix)

    raise ValueError('number too large')


def get_attr(element, match_list):
    """ function to convert an xml node element with attributes, to a dict """

    attr_list = {}
    for node in element.getchildren():
        if node.tag in match_list:
            attr_list[node.tag] = node.text

    return attr_list


def version_ok(this_version, target_version):
    """
    Compare one version to another, returning a boolean for the src version
    being >= target version
    """

    this_version = str(this_version)
    target_version = str(target_version)

    # Account for version strings passes not in X.Y format
    if this_version.count('.') > 1:
        this_version = major_minor(this_version)

    if target_version.count('.') > 1:
        target_version = major_minor(target_version)

    (this_major, this_minor) = this_version.split('.')
    (tgt_major, tgt_minor) = target_version.split('.')

    if (int(this_major) >= int(tgt_major) and
            (int(this_minor) >= int(tgt_minor))):
        return True
    else:
        return False


def major_minor(version_string):
    """
    return the major.minor of a full version string
    """

    return '.'.join(version_string.split('.')[:2])
