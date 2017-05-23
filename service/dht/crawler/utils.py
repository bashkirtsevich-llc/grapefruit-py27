#!/usr/bin/env python
# coding=utf-8

import math
import socket
import struct
from random import randint


def generate_id(length):
    return reduce(lambda r, _: r + chr(randint(0, 255)), xrange(length), "")


def decode_nodes(message):
    nodes = []
    if len(message) % 26 != 0:
        return nodes

    for i in xrange(0, len(message), 26):
        node_id = message[i: i + 20]

        try:
            ip = socket.inet_ntoa(message[i + 20: i + 24])  # from network order to IP address
            port = struct.unpack("!H", message[i + 24: i + 26])[0]  # "!" means to read by network order
        except:
            continue

        nodes.append([node_id, (ip, port)])

    return nodes


def encode_nodes(nodes):
    message = ""
    for node in nodes:
        try:
            ip_message = socket.inet_aton(node[1][0])
            port_message = struct.pack("!H", node[1][1])
        except:
            continue  # from IP address to network order
        message = message + node[0] + ip_message + port_message

    return message


def xor(node_one_id, node_two_id):
    result = 0

    length = len(node_one_id)
    for i in xrange(length):
        result = (result << 8) + (ord(node_one_id[i]) ^ ord(node_two_id[i]))

    return result


def get_routing_table_index(distance):
    if distance == 0:
        return 0
    else:
        return int(math.floor(math.log(math.fabs(distance), 2.0)))
