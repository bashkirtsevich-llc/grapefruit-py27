import hashlib
from uuid import uuid4


def sha1(s):
    if not isinstance(s, str):
        s = str(s)
    return hashlib.sha1(s).digest()


def generate_node_id():
    return sha1(uuid4().bytes)


def generate_peer_id():
    return "-GC0000-" + generate_node_id()[8:]
