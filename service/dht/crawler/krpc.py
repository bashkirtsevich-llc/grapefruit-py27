#!/usr/bin/env python
# coding=utf-8

import time
import random
import socket

from utils import generate_id
from utils import get_routing_table_index
from utils import xor
from utils import encode_nodes
from utils import decode_nodes
from ..common_utils import generate_node_id

from threading import Lock, Thread
from config import INITIAL_NODES, UDP_SERVER_BANDWIDTH
from bencode import bencode, bdecode


class KRPC(object):
    def __init__(self, address):
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.__socket.bind(address)

        self._latency = 0.001
        self._bandwidth = UDP_SERVER_BANDWIDTH
        self._bytes_send = 0
        self._bytes_recv = 0
        self._time_created = time.time()

    def __del__(self):
        self.__socket.close()

    def _send(self, data, address):
        try:
            self._bytes_send += len(data)

            connectionDuration = time.time() - self._time_created
            requiredDuration = self._bytes_send / self._bandwidth
            time.sleep(max(requiredDuration - connectionDuration, self._latency))

            self.__socket.sendto(data, address)
        except:
            pass

    def _receive(self):
        try:
            result = self.__socket.recvfrom(65536)

            if result:
                data, _ = result

                self._bytes_recv += len(data)

                connectionDuration = time.time() - self._time_created
                requiredDuration = self._bytes_recv / self._bandwidth
                time.sleep(max(requiredDuration - connectionDuration, self._latency))

            return result
        except:
            return None

    def _get_sock_name(self):
        return self.__socket.getsockname()


class DHTProtocol(KRPC):
    K = 8
    NEW_K = 1500
    TABLE_NUM = 160
    TOKEN_LENGTH = 5
    TRANS_ID_LENGTH = 2

    def __init__(self, node_id, routing_table, address, **kwargs):
        super(DHTProtocol, self).__init__(address)
        self.node_id = node_id
        self.routing_table = routing_table

        self._on_ping = kwargs.get("on_ping", None)
        self._on_find_nodes = kwargs.get("on_find_nodes", None)
        self._on_get_peers = kwargs.get("on_get_peers", None)
        self._on_announce = kwargs.get("on_announce", None)
        self._on_save_routing_table = kwargs.get("on_save_routing_table", None)

        self.routing_table_lock = Lock()

    def _send_message(self, message, address):
        self._send(bencode(message), address)

    def get_k_closest_nodes(self, node_id):
        r_table_index = get_routing_table_index(xor(self.node_id, node_id))

        k_closest_nodes = []

        index = r_table_index
        while index >= 0 and len(k_closest_nodes) < DHTProtocol.K:
            for node in self.routing_table[index]:
                if len(k_closest_nodes) < DHTProtocol.K:
                    k_closest_nodes.append(node)
                else:
                    break
            index -= 1

        index = r_table_index + 1
        while index < 160 and len(k_closest_nodes) < DHTProtocol.K:
            for node in self.routing_table[index]:
                if len(k_closest_nodes) < DHTProtocol.K:
                    k_closest_nodes.append(node)
                else:
                    break
            index += 1

        return k_closest_nodes

    def add_nodes_to_routing_table(self, nodes):
        with self.routing_table_lock:
            for node in nodes:
                r_table_index = get_routing_table_index(xor(node[0], self.node_id))
                if len(self.routing_table[r_table_index]) < DHTProtocol.NEW_K:
                    self.routing_table[r_table_index].append(node)
                else:
                    if random.randint(0, 1):
                        index = random.randint(0, DHTProtocol.NEW_K - 1)
                        self.routing_table[r_table_index][index] = node
                    else:
                        self.find_node(node)

    def handle_ping_query(self, data, address):
        response = {
            "t": data["t"],
            "y": "r",
            "r": {
                "id": self.node_id
            }
        }

        self._send_message(response, address)

        if self._on_ping is not None:
            self._on_ping()

    def handle_find_nodes_query(self, data, address):
        target_node_id = data["a"]["target"]
        r_table_index = get_routing_table_index(xor(self.node_id, target_node_id))

        response_nodes = []
        for node in self.routing_table[r_table_index]:
            if node[0] == target_node_id:
                response_nodes.append(node)
                break

        if len(response_nodes) == 0:
            response_nodes = self.get_k_closest_nodes(target_node_id)

        node_message = encode_nodes(response_nodes)

        response = {
            "t": data["t"],
            "y": "r",
            "r": {
                "id": self.node_id,
                "nodes": node_message
            }
        }

        self._send_message(response, address)

        if self._on_find_nodes is not None:
            self._on_find_nodes(target_node_id)

    def handle_get_peers_query(self, data, address):
        info_hash = data["a"]["info_hash"]

        response = {
            "t": data["t"],
            "y": "r",
            "r": {
                "id": self.node_id,
                "token": generate_id(DHTProtocol.TOKEN_LENGTH),
                "nodes": encode_nodes(self.get_k_closest_nodes(info_hash))
            }
        }

        self._send_message(response, address)

        if self._on_get_peers is not None:
            self._on_get_peers(info_hash)

    def handle_announce_peer_query(self, data, address):
        arguments = data["a"]
        info_hash = arguments["info_hash"]
        port = arguments["port"]

        host, _ = address

        response = {
            "t": data["t"],
            "y": "r",
            "r": {
                "id": self.node_id
            }
        }

        self._send_message(response, address)

        if self._on_announce is not None:
            self._on_announce(info_hash, host, port)

    def handle_find_node_response(self, data, address):
        node_message = data["r"]["nodes"]
        nodes = decode_nodes(node_message)
        self.add_nodes_to_routing_table(nodes)

    def handle(self, data, address):
        try:
            data = bdecode(data)
        except:
            return

        query_handle_function = {
            "ping": self.handle_ping_query,
            "find_node": self.handle_find_nodes_query,
            "get_peers": self.handle_get_peers_query,
            "announce_peer": self.handle_announce_peer_query
        }

        try:
            msg_type = data["y"]

            if msg_type == "q":
                if data["q"] in query_handle_function.keys():
                    query_handle_function[data["q"]](data, address)

            elif msg_type == "r":
                if "nodes" in data["r"]:
                    self.handle_find_node_response(data, address)

        except KeyError:
            pass

    def __server(self):
        while True:
            receive_info = self._receive()
            if receive_info is not None:
                self.handle(*receive_info)

    def __client(self):
        if len(self.routing_table) == 0:
            nodes = []
            self.routing_table = map(lambda i: [], range(DHTProtocol.TABLE_NUM))

            for initial_node in INITIAL_NODES:
                nodes.append([generate_node_id(), initial_node])

            nodes.append([self.node_id, self._get_sock_name()])
            self.add_nodes_to_routing_table(nodes)

        timestamps = {
            "save_routing_table": time.time()
        }

        while True:
            with self.routing_table_lock:
                timestamp = time.time()

                for bucket in self.routing_table:
                    for node in bucket:
                        # Decrease frequency. Can request from one node each 10 seconds.
                        if node[0] not in timestamps or timestamp - timestamps[node[0]] > 10.0:
                            self.find_node(node)

                            timestamps[node[0]] = timestamp

                if timestamp - timestamps["save_routing_table"] > 120.0:  # Save routing table each 120 seconds
                    if self._on_save_routing_table is not None:
                        self._on_save_routing_table(self.node_id,
                                                    self.routing_table,
                                                    self._get_sock_name())

                        timestamps["save_routing_table"] = timestamp

            time.sleep(5)

    def find_node(self, node):
        query = {
            "t": generate_id(DHTProtocol.TRANS_ID_LENGTH),
            "y": "q",
            "q": "find_node",
            "a": {
                "id": self.node_id,
                "target": generate_node_id()
            }
        }

        self._send_message(query, tuple(node[1]))

    def start(self):
        client_thread = Thread(target=self.__client)
        server_thread = Thread(target=self.__server)

        client_thread.start()
        server_thread.start()
