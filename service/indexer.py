from binascii import unhexlify
from pymongo import MongoClient
from torrent import load_torrent
from time import sleep
from random import shuffle


def __store_metadata(db, metadata, try_load_metadata):
    try:
        key = {"info_hash": metadata["info_hash"]}

        value = {"name": metadata["name"],
                 "files": map(lambda f: {"path": f["path"],
                                         "length": f["length"]},
                              metadata["files"])}

        db.torrents.update(key, {"$set": value,
                                 "$unset": {"attempt": ""}})
    finally:
        __index_next_info_hash(db, try_load_metadata)


def __shuffle(src_list):
    shuffle(src_list)
    return src_list


def __index_next_info_hash(db, try_load_metadata, torrents=None):
    while True:
        sleep(60)  # Wait 60 seconds

        # Remove torrents with too much attempts count (ignore after 10 attempts)
        db.torrents.remove({"$and": [{"name": {"$exists": False}},
                                     {"files": {"$exists": False}},
                                     {"attempt": {"$gte": 10}}]}
                           )

        # Find candidates to load
        torrents_list = torrents or __shuffle(
            list(db.torrents.find(
                {"$and": [{"name": {"$exists": False}},
                          {"files": {"$exists": False}},
                          {"attempt": {"$lt": 10}}]}
            ))
        )

        if torrents_list:
            item = torrents_list[0]
            info_hash = unhexlify(item["info_hash"])

            # Increase torrent attempts count
            db.torrents.update({"info_hash": info_hash}, {"$set": {"attempt", item.get("attempt", 0) + 1}})

            args = dict(
                info_hash=info_hash,
                on_torrent_loaded=lambda metadata: __store_metadata(db, metadata, try_load_metadata),
                on_torrent_not_found=lambda: __index_next_info_hash(db, try_load_metadata, torrents_list[1:])
            )
            try_load_metadata(**args)

            break


def start_indexer(mongodb_uri, port, node_id=None, bootstrap_node_address=("router.bittorrent.com", 6881)):
    mongodb_client = MongoClient(mongodb_uri)
    try:
        db = mongodb_client.grapefruit

        load_torrent(bootstrap_node_address, port,
                     node_id=node_id,
                     on_bootstrap_done=lambda try_load_metadata: __index_next_info_hash(db, try_load_metadata)
                     )
    finally:
        mongodb_client.close()
