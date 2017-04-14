from binascii import unhexlify, hexlify
from pymongo import MongoClient
from datetime import datetime
from threading import Lock
from metadata_loader import metadata_loader
from dht.crawler.node import Node

import collections


def __get_routing_tables(db, db_lock):
    with db_lock:
        tables = list(db.crawler_route.find())

        for table in tables:
            table["node_id"] = unhexlify(table["node_id"])
            for bucket in table["routing_table"]:
                for node in bucket:
                    node[0] = unhexlify(node[0])

        return tables


def __store_routing_table(db, db_lock, local_node_id, routing_table, address):
    with db_lock:
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
    db.hashes.insert({
        "info_hash": info_hash,
        "timestamp": datetime.utcnow()
    })


def __encode_utf8(data):
    if isinstance(data, basestring):
        return data.encode('utf-8')
    elif isinstance(data, collections.Mapping):
        return dict(map(__encode_utf8, data.iteritems()))
    elif isinstance(data, collections.Iterable):
        return type(data)(map(__encode_utf8, data))
    else:
        return data


def __store_metadata(db, db_lock, metadata):
    with db_lock:
        if db.torrents.find_one({"info_hash": metadata["info_hash"]}) is None:
            db.torrents.insert_one(__encode_utf8(metadata))


def __handle_get_peers_event(db, db_lock, info_hash, try_load_metadata):
    with db_lock:
        torrent_hash = hexlify(info_hash)
        __store_info_hash(db, torrent_hash)

        if db.torrents.find_one({"info_hash": torrent_hash}) is None:
            try_load_metadata(info_hash,
                              lambda metadata: __store_metadata(
                                  db, db_lock, metadata))


def __handle_announce_event(db, db_lock, info_hash, announce_host, announce_port, try_load_metadata):
    with db_lock:
        torrent_hash = hexlify(info_hash)
        __store_info_hash(db, torrent_hash)

        if db.torrents.find_one({"info_hash": torrent_hash}) is None:
            try_load_metadata(info_hash,
                              lambda metadata: __store_metadata(
                                  db, db_lock, metadata))


def __start_crawler_node(db, db_lock, crawler_port, crawler_node_id, try_load_metadata):
    arguments = {
        "node_id": crawler_node_id,
        "routing_table": None,
        "address": ("0.0.0.0", crawler_port),
        "on_save_routing_table":
            lambda local_node_id, routing_table, address: __store_routing_table(
                db, db_lock, local_node_id, routing_table, address),
        "on_get_peers":
            lambda info_hash: __handle_get_peers_event(
                db, db_lock, info_hash, try_load_metadata),
        "on_announce":
            lambda info_hash, announce_host, announce_port: __handle_announce_event(
                db, db_lock, info_hash, announce_host, announce_port, try_load_metadata)
    }

    routing_tables = __get_routing_tables(db, db_lock)

    if routing_tables and routing_tables[0]["node_id"] == crawler_node_id:
        arguments["routing_table"] = routing_tables[0]["routing_table"]

    node = Node(**arguments)
    node.protocol.start()


def start_server(mongodb_uri, crawler_port, server_port, crawler_node_id=None, server_node_id=None):
    mongodb_client = MongoClient(mongodb_uri)
    try:
        db = mongodb_client.grapefruit
        db_lock = Lock()

        metadata_loader("router.bittorrent.com", 6881, server_port,
                        node_id=server_node_id,
                        on_bootstrap_done=lambda cb: __start_crawler_node(
                            try_load_metadata=cb,
                            db=db,
                            db_lock=db_lock,
                            crawler_port=crawler_port,
                            crawler_node_id=crawler_node_id)
                        )
    finally:
        mongodb_client.close()
