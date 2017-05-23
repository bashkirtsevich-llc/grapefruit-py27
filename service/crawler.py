from binascii import hexlify, unhexlify
from pymongo import MongoClient
from datetime import datetime
from dht.common_utils import generate_node_id
from dht.crawler.krpc import DHTProtocol


def __try_load_routing_table(db, local_node_host, local_node_port, local_node_id=None):
    cond_list = [{"local_node_host": local_node_host},
                 {"local_node_port": local_node_port}]

    if local_node_id:
        cond_list.append({"local_node_id": local_node_id})

    table = db.crawler_route.find_one({"$and": cond_list})

    if table:
        # Restore routing table
        return {
            # We must unhexlify all identifiers
            "buckets": map(
                lambda bucket: map(
                    lambda node: [
                        unhexlify(node[0]),  # node id (hex)
                        node[1]],  # node address tuple (host, port)
                    bucket),
                table["buckets"]),
            "local_node_host": table["local_node_host"],
            "local_node_port": table["local_node_port"],
            "local_node_id": unhexlify(table["local_node_id"])
        }
    else:
        # Generate empty routing table
        return {
            "buckets": [],
            "local_node_host": local_node_host,
            "local_node_port": local_node_port,
            "local_node_id": local_node_id if local_node_id else generate_node_id()
        }


def __store_routing_table(db, local_node_id, address, buckets):
    coll = db.crawler_route

    node_id_hex = hexlify(local_node_id)

    buckets_hex = map(
        lambda bucket: map(
            lambda node: [
                hexlify(node[0]),  # node id (hex)
                node[1]],  # node address tuple (host, port)
            bucket),
        buckets)

    if coll.find_one({"local_node_id": node_id_hex}):
        coll.update({"local_node_id": node_id_hex},
                    {"$set": {"buckets": buckets_hex}})
    else:
        coll.insert({
            "buckets": buckets_hex,
            "local_node_id": node_id_hex,
            "local_node_host": address[0],
            "local_node_port": address[1]
        })


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

        routing_table = __try_load_routing_table(db, "0.0.0.0", port, node_id)

        arguments = {
            "node_id": routing_table["local_node_id"],
            "routing_table": routing_table["buckets"],
            "address": (routing_table["local_node_host"],
                        routing_table["local_node_port"]),
            "on_save_routing_table":
                lambda local_node_id, routing_table, address:
                __store_routing_table(db, local_node_id, address, routing_table),
            "on_get_peers":
                lambda info_hash:
                __store_info_hash(db, info_hash),
            "on_announce":
                lambda info_hash, announce_host, announce_port:
                __store_info_hash(db, info_hash)
        }

        protocol = DHTProtocol(**arguments)
        protocol.start()
    finally:
        mongodb_client.close()
