#!/usr/bin/env python
# coding=utf-8

from krpc import DHTProtocol
from ..common_utils import generate_node_id


class Node(object):
    def __init__(self, node_id=None, routing_table=None, address=None, **kwargs):
        self._node_id = node_id if node_id is not None else generate_node_id()
        self._routing_table = routing_table if routing_table is not None else []
        self._protocol = DHTProtocol(self._node_id, self._routing_table, address, **kwargs)

    @property
    def node_id(self):
        return self._node_id

    @property
    def routing_table(self):
        return self._routing_table

    @property
    def protocol(self):
        return self._protocol
