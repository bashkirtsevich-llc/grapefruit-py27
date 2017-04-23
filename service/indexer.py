from pymongo import MongoClient
from torrent import load_torrent
from time import sleep
from random import choice


def __store_metadata(db, metadata, try_load_metadata):
    try:
        key = {"info_hash": metadata["info_hash"]}

        value = {"name": metadata["name"],
                 "files": map(lambda f: {"path": f["path"],
                                         "length": f["length"]},
                              metadata["files"])}

        db.torrents.update(key, {"$set": value})
    finally:
        __index_next_info_hash(db, try_load_metadata)


def __index_next_info_hash(db, try_load_metadata):
    while True:
        torrents = list(db.torrents.find(
            {"$and": [
                {"name": {"$exists": False}},
                {"files": {"$exists": False}}]
            }
        ))

        if torrents:
            try_load_metadata(choice(torrents)["info_hash"],
                              lambda metadata: __store_metadata(db, metadata, try_load_metadata),
                              lambda: __index_next_info_hash(db, try_load_metadata))

            break

        sleep(10)


def start_indexer(mongodb_uri, port, node_id=None, bootstrap_node_address=("router.bittorrent.com", 6881)):
    mongodb_client = MongoClient(mongodb_uri)
    try:
        db = mongodb_client.grapefruit

        load_torrent(bootstrap_node_address, port,
                     node_id=node_id,
                     on_bootstrap_done=lambda try_load_metadata: __index_next_info_hash(
                         db=db,
                         try_load_metadata=try_load_metadata)
                     )
    finally:
        mongodb_client.close()
