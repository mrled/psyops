import socket
import fcntl
import struct


def get_ip_address(ifname):
    """Get the IP address of a network interface by name, e.g. eth0."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(
        fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", ifname[:15].encode("utf-8")))[20:24]  # SIOCGIFADDR
    )
