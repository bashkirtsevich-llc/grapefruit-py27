from binascii import unhexlify, hexlify
from pymongo import MongoClient
from datetime import datetime

from metadata_loader import metadata_loader
from dht.crawler.node import Node


def start_server(mongodb_uri, crawler_port, server_port, crawler_node_id=None, server_node_id=None):
    mongo_client = MongoClient(mongodb_uri)
    try:
        db = mongo_client.grapefruit

        def get_routing_tables():
            tables = list(db.crawler_route.find())

            for table in tables:
                table["node_id"] = unhexlify(table["node_id"])
                for bucket in table["routing_table"]:
                    for node in bucket:
                        node[0] = unhexlify(node[0])

            return tables

        def store_routing_table(local_node_id, routing_table, address):
            coll = db.crawler_route

            local_node_id = hexlify(local_node_id)
            for bucket in routing_table:
                for node in bucket:
                    node[0] = hexlify(node[0])

            if coll.find_one({"node_id": local_node_id}):
                coll.update({"node_id": local_node_id}, {"$set": {"routing_table": routing_table}})
            else:
                coll.insert({
                    "node_id": local_node_id,
                    "routing_table": routing_table
                })

            for bucket in routing_table:
                for node in bucket:
                    node[0] = unhexlify(node[0])

        def store_info_hash(info_hash):
            coll = db.hashes

            if coll.find_one({"info_hash": info_hash}):
                coll.update({"info_hash": info_hash},
                            {"$set": {"updated": datetime.utcnow()}})
            else:
                coll.insert({
                    "info_hash": info_hash,
                    "added": datetime.utcnow()
                })

        def store_torrent_metadata(metadata):
            if db.torrents.find_one({"info_hash": metadata["info_hash"]}) is not None:
                db.torrents.insert_one(metadata)

        def start_crawler_node(try_load_metadata):
            def handle_announce_event(info_hash, announce_host, announce_port):
                store_info_hash(hexlify(info_hash))

                if db.torrents.find_one({"info_hash": hexlify(info_hash)}) is None:
                    try_load_metadata(info_hash, store_torrent_metadata)

            def handle_get_peers_event(info_hash):
                store_info_hash(hexlify(info_hash))

                if db.torrents.find_one({"info_hash": hexlify(info_hash)}) is None:
                    try_load_metadata(info_hash, store_torrent_metadata)

            arguments = {
                "node_id": crawler_node_id,
                "routing_table": None,
                "address": ("0.0.0.0", crawler_port),
                "on_get_peers": handle_get_peers_event,
                "on_announce": handle_announce_event,
                "on_save_routing_table": store_routing_table
            }

            routing_tables = get_routing_tables()

            if routing_tables and routing_tables[0]["node_id"] == crawler_node_id:
                arguments["routing_table"] = routing_tables[0]["routing_table"]

            Node(**arguments).protocol.start()

        metadata_loader("router.bittorrent.com", 6881, server_port, node_id=server_node_id,
                        on_bootstrap_done=start_crawler_node)
    finally:
        mongo_client.close()
