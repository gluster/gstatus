
import socket
import fcntl
import struct
import array


# import  gstatus.functions.config as cfg

def port_open(hostname, port, scan_timeout=0.05):
    """ return boolean denoting whether a given port on a host is open or not """

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(scan_timeout)

    state = True if s.connect_ex((hostname, port)) == 0 else False

    return state


def ip_to_host(addr):
    """ convert an IP address to a host name, returning shortname and fqdn to the 
        caller
    """

    try:
        fqdn = socket.gethostbyaddr(addr)[0]
        shortname = fqdn.split('.')[0]
        if fqdn == shortname:
            fqdn = ""

    except:
        # can't resolve it, so default to the address given
        shortname = addr
        fqdn = ""

    return shortname, fqdn


def host_to_ip(hostname):
    """ provide a IP address for a given fqdn """

    try:
        return socket.gethostbyname(hostname)
    except:
        return hostname


def is_ip(host_string):
    """ Quick method to determine whether a string is an IP address or not """

    try:
        x = socket.inet_aton(host_string)
        response = True
    except:
        response = False

    return response


def host_aliases(host):
    """ for any given host attempt to return an alias list of names/IP """

    alias_list = [host]
    fqdn = ''
    shortname = ''
    ip_addr = ''

    if is_ip(host):

        try:
            fqdn = socket.gethostbyaddr(host)[0]

        except:
            # could get "socket.herror: [Errno 1] Unknown host"
            # indicating that reverse DNS is not working for this IP

            # If this is an IP on the local machine, use gethostname()
            if host in get_ipv4_addr():
                fqdn = socket.gethostname()
            else:
                # however, if the IP is foreign and not resolving check
                # /etc/hosts for an answer
                with open('/etc/hosts') as hosts_file:
                    ip_match = [host_entry for host_entry in hosts_file.readlines() if host in host_entry]
                if ip_match:
                    fqdn = ip_match[0].split()[1]

        shortname = fqdn.split('.')[0]
        alias_list.append(fqdn)
        alias_list.append(shortname)

    else:
        try:
            if '.' in host:
                shortname = host.split('.')[0]
                alias_list.append(shortname)
            else:
                fqdn = socket.gethostbyname_ex(host)[0]
                alias_list.append(fqdn)

            ip_addr = socket.gethostbyname(host)
        except:
            # do nothing
            pass

        alias_list.append(ip_addr)

    return sorted(alias_list)


def get_ipv4_addr():
    """ return a list of ipv4 addresses on this host ignoring specific interfaces
        that gluster wouldn't be using - tun/tap, virbrX etc
    """

    struct_size = 40        # 64bit environment - each name/IP pair is 40 bytes
    SIOCGIFCONF = 35090     # addr from http://pydoc.org/1.6/SOCKET.html
    __bytes = 4096          # buffer size to use
    ignored_ifaces = ('lo', 'virbr', 'tun', 'tap')

    sck = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    names = array.array('B', bytearray('\0' * __bytes, 'utf-8'))
    outbytes = struct.unpack('iL', fcntl.ioctl(
        sck.fileno(),
        SIOCGIFCONF,
        struct.pack('iL', __bytes, names.buffer_info()[0])))[0]

    namestr = names.tobytes()

    if_list = [(namestr[i:i + 16].decode('utf-8').split('\0', 1)[0],
                socket.inet_ntoa(namestr[i + 20:i + 24]))
               for i in range(0, outbytes, struct_size)]

    return [ifaddr for ifname, ifaddr in if_list
            if not ifname.startswith(ignored_ifaces)]
