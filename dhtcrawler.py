#!/usr/bin/env python
# coding=utf-8

import sys
from optparse import OptionParser
import pymongo
import utility
import datetime
from torrent_loader import TorrentLoader
from node import Node
from bencode import bdecode


def start_crawler(mongodb_uri):
    parser = OptionParser(version="0.1", epilog="Crawl DHT network to sniff torrent hashes", description="DHT Crawler")
    parser.add_option("-H", "--host", dest="server_host", default="0.0.0.0",
                      help="Local UDP server network address (default: 0.0.0.0)")
    parser.add_option("-P", "--port", dest="server_port", default=12346,
                      help="Local UDP server network port (default: 12346)")
    parser.add_option("-I", "--node_id", dest="node_id", default=None,
                      help="DHT server local node id")
    parser.add_option("-F", "--forcibly", dest="forcibly", default=False,
                      help="Forcibly override stored node configuration (default: False)")

    (opts, args) = parser.parse_args(sys.argv[1:])

    client = pymongo.MongoClient(mongodb_uri)
    try:
        database = client.dhtcrawler

        loaders = {}

        def handle_ping_event():
            print "Receive ping"

        def handle_find_nodes_event():
            print "Find nodes"

        def get_routing_tables():
            routing_tables = list(database.routing_tables.find())

            for routing_table in routing_tables:
                routing_table["node_id"] = utility.from_hex_to_byte(routing_table["node_id"])
                for bucket in routing_table["routing_table"]:
                    for node in bucket:
                        node[0] = utility.from_hex_to_byte(node[0])

            return routing_tables

        def handle_save_routing_table(node_id, routing_table, address):
            coll = database.routing_tables

            node_id = utility.from_byte_to_hex(node_id)
            for bucket in routing_table:
                for node in bucket:
                    node[0] = utility.from_byte_to_hex(node[0])

            if coll.find_one({"node_id": node_id}):
                coll.update({"node_id": node_id}, {"$set": {"routing_table": routing_table}})
            else:
                coll.insert({
                    "node_id": node_id,
                    "address": list(address),
                    "routing_table": routing_table
                })

            for bucket in routing_table:
                for node in bucket:
                    node[0] = utility.from_hex_to_byte(node[0])

        def handle_announce_event(info_hash, host, announce_port):
            print "Announce hash", utility.from_byte_to_hex(info_hash), host, announce_port

            coll = database.info_hashes

            coll.insert({
                "value": utility.from_byte_to_hex(info_hash),
                "host": host,
                "port": announce_port,
                "date": datetime.datetime.utcnow()
            })

            torrents = database.torrents

            btih = utility.from_byte_to_hex(info_hash)

            if not btih in loaders and not torrents.find_one({"info_hash": btih}):
                def save_metadata(metadata):
                    torrents.insert({
                        "info_hash": btih,
                        "metadata": bdecode(metadata)
                    })

                def release_loader():
                    del loaders[info_hash]

                loader = loaders[btih] = TorrentLoader(host, announce_port, info_hash,
                                                       on_metadata_loaded=save_metadata,
                                                       on_finish=release_loader)

                loader.start()

        def handle_get_peers_event(info_hash):
            print "Get peers", utility.from_byte_to_hex(info_hash)

            coll = database.get_peer_info_hashes

            coll.insert({
                "value": utility.from_byte_to_hex(info_hash),
                "timestamp": datetime.datetime.utcnow()
            })

        arguments = {
            "node_id": opts.node_id,
            "routing_table": None,
            "address": (opts.server_host, opts.server_port),
            "on_ping": handle_ping_event,
            "on_find_nodes": handle_find_nodes_event,
            "on_get_peers": handle_get_peers_event,
            "on_announce": handle_announce_event,
            "on_save_routing_table": handle_save_routing_table
        }

        routing_tables = get_routing_tables()

        if len(routing_tables) > 0 and not opts.forcibly:
            for routing_table in routing_tables:
                arguments["node_id"] = routing_table["node_id"]
                arguments["routing_table"] = routing_table["routing_table"]
                arguments["address"] = tuple(routing_table["address"])

                break

        nodes = []

        node = Node(**arguments)
        node.protocol.start()

        nodes.append(node)
    finally:
        client.close()
