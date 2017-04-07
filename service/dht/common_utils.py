import hashlib
import socket
import struct
from uuid import uuid4


def sha1(s):
    if not isinstance(s, str):
        s = str(s)
    return hashlib.sha1(s).digest()


def generate_node_id():
    return sha1(uuid4().bytes)

def generate_peer_id():
    return "-GC0000-" + generate_node_id()[:8]


def decode_nodes(message):
    result = []
    if len(message) % 26 != 0:
        return result

    for i in range(0, len(message), 26):
        node_id = message[i: i + 20]

        try:
            ip = socket.inet_ntoa(message[i + 20: i + 24])  # from network order to IP address
            port = struct.unpack("!H", message[i + 24: i + 26])[0]  # "!" means to read by network order
        except:
            continue

        result.append([node_id, ip, port])

    return result


def decode_values(values):
    return map(lambda value: (socket.inet_ntoa(value[:4]),
                              struct.unpack("!H", value[4: 6])[0]), values)


def encode_values(values):
    return map(lambda value: socket.inet_aton(value[0] + struct.pack("!H", value[1])), values)


def encode_nodes(nodes):
    result = ""
    for node in nodes:
        try:
            ip_message = socket.inet_aton(node.ip)
            port_message = struct.pack("!H", node.port)
        except:
            continue  # from IP address to network order

        result = result + node.id + ip_message + port_message

    return result
