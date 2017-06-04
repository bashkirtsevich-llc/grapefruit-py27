"""
General catchall for functions that don't make sense as methods.
"""
import datetime
import math
import operator
import socket
import struct
from uuid import uuid4

from twisted.internet import defer

from service.dht.common_utils import sha1


class OrderedSet(list):
    """
    Acts like a list in all ways, except in the behavior of the :meth:`push` method.
    """

    def push(self, thing):
        """
        1. If the item exists in the list, it's removed
        2. The item is pushed to the end of the list
        """
        if thing in self:
            self.remove(thing)
        self.append(thing)


token_salt = uuid4().bytes


def generate_token(ip, port):
    return sha1(token_salt + str(ceil_dt(datetime.datetime.now())) + ip + str(port))


def verify_token(ip, port, token):
    return generate_token(ip, port) == token


def ceil_dt(dt):
    nsecs = dt.minute * 60 + dt.second + dt.microsecond * 1e-6
    delta = math.ceil(nsecs / 300) * 300 - nsecs
    return dt + datetime.timedelta(seconds=delta)


def deferred_dict(d):
    """
    Just like a :class:`defer.DeferredList` but instead accepts and returns a :class:`dict`.

    Args:
        d: A :class:`dict` whose values are all :class:`defer.Deferred` objects.

    Returns:
        :class:`defer.DeferredList` whose callback will be given a dictionary whose
        keys are the same as the parameter :obj:`d` and whose values are the results
        of each individual deferred call.
    """
    if len(d) == 0:
        return defer.succeed({})

    def handle(results, names):
        rvalue = {}
        for index in range(len(results)):
            rvalue[names[index]] = results[index][1]
        return rvalue

    dl = defer.DeferredList(d.values())
    return dl.addCallback(handle, d.keys())


def shared_prefix(args):
    """
    Find the shared prefix between the strings.

    For instance:

        sharedPrefix(['blahblah', 'blahwhat'])

    returns 'blah'.
    """
    i = 0
    while i < min(map(len, args)):
        if len(set(map(operator.itemgetter(i), args))) != 1:
            break
        i += 1
    return args[0][:i]


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
    result = []

    for value in values:
        try:
            result.append((socket.inet_ntoa(value[:4]),
                           struct.unpack("!H", value[4: 6])[0]))
        except:
            continue

    return result


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
