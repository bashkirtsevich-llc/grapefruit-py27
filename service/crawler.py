from binascii import hexlify, unhexlify
from pymongo import MongoClient
from datetime import datetime
from dht.common_utils import generate_node_id
from dht.crawler.krpc import DHTProtocol


def __get_routing_tables(db):
    tables = list(db.crawler_route.find())

    for table in tables:
        table["node_id"] = unhexlify(table["node_id"])
        for bucket in table["routing_table"]:
            for node in bucket:
                node[0] = unhexlify(node[0])

    return tables


def __store_routing_table(db, local_node_id, routing_table):
    coll = db.crawler_route

    local_node_id = hexlify(local_node_id)
    for bucket in routing_table:
        for node in bucket:
            node[0] = hexlify(node[0])

    if coll.find_one({"node_id": local_node_id}):
        coll.update({"node_id": local_node_id},
                    {"$set": {"routing_table": routing_table}})
    else:
        coll.insert({
            "node_id": local_node_id,
            "routing_table": routing_table
        })

    for bucket in routing_table:
        for node in bucket:
            node[0] = unhexlify(node[0])


def __store_info_hash(db, info_hash):
    hex_info_hash = hexlify(info_hash)

    db.hashes.insert({
        "info_hash": hex_info_hash,
        "timestamp": datetime.utcnow()
    })

    # Store "info_hash" in "torrents" collection for quick find, when loader will load data
    if db.torrents.find_one({"info_hash": hex_info_hash}) is None:
        db.torrents.insert_one({"info_hash": hex_info_hash})


def start_crawler(mongodb_uri, port, node_id=None):
    mongodb_client = MongoClient(mongodb_uri)
    try:
        db = mongodb_client.grapefruit

        arguments = {
            "node_id": node_id if node_id else generate_node_id(),
            "routing_table": [],
            "address": ("0.0.0.0", port),
            "on_save_routing_table":
                lambda local_node_id, routing_table, address:
                __store_routing_table(db, local_node_id, routing_table),
            "on_get_peers":
                lambda info_hash:
                __store_info_hash(db, info_hash),
            "on_announce":
                lambda info_hash, announce_host, announce_port:
                __store_info_hash(db, info_hash)
        }

        routing_tables = __get_routing_tables(db)

        if routing_tables and routing_tables[0]["node_id"] == node_id:
            arguments["routing_table"] = routing_tables[0]["routing_table"]

        protocol = DHTProtocol(**arguments)
        protocol.start()
    finally:
        mongodb_client.close()
