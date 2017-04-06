#!/usr/bin/env python
# coding=utf-8

import binascii
import datetime

from pymongo import MongoClient

from service.dht.crawler.node import Node


def start_crawler(mongodb_uri, host, port, node_id=None):
    client = MongoClient(mongodb_uri)
    try:
        database = client.grapefruit

        def get_routing_tables():
            routing_tables = list(database.routing_tables.find())

            for routing_table in routing_tables:
                routing_table["node_id"] = binascii.unhexlify(routing_table["node_id"])
                for bucket in routing_table["routing_table"]:
                    for node in bucket:
                        node[0] = binascii.unhexlify(node[0])

            return routing_tables

        def handle_save_routing_table(local_node_id, routing_table, address):
            coll = database.routing_tables

            local_node_id = binascii.hexlify(local_node_id)
            for bucket in routing_table:
                for node in bucket:
                    node[0] = binascii.hexlify(node[0])

            if coll.find_one({"node_id": local_node_id}):
                coll.update({"node_id": local_node_id}, {"$set": {"routing_table": routing_table}})
            else:
                coll.insert({
                    "node_id": local_node_id,
                    "routing_table": routing_table
                })

            for bucket in routing_table:
                for node in bucket:
                    node[0] = binascii.unhexlify(node[0])

        def handle_find_nodes_event(target_node_id):
            print "Find nodes"

        def handle_announce_event(info_hash, announce_host, announce_port):
            print "Announce hash", binascii.hexlify(info_hash), announce_host, announce_port

        def handle_get_peers_event(info_hash):
            print "Get peers", binascii.hexlify(info_hash)

            coll = database.get_peer_info_hashes

            coll.insert({
                "value": binascii.hexlify(info_hash),
                "timestamp": datetime.datetime.utcnow()
            })

        arguments = {
            "node_id": node_id,
            "routing_table": None,
            "address": (host, port),
            "on_find_nodes": handle_find_nodes_event,
            "on_get_peers": handle_get_peers_event,
            "on_announce": handle_announce_event,
            "on_save_routing_table": handle_save_routing_table
        }

        routing_tables = get_routing_tables()

        if routing_tables and routing_tables[0]["node_id"] == node_id:
            arguments["routing_table"] = routing_tables[0]["routing_table"]

        nodes = []

        node = Node(**arguments)
        node.protocol.start()

        nodes.append(node)
    finally:
        client.close()
