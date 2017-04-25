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


def __index_next_info_hash(db, try_load_metadata, torrents=None):
    MAX_ATTEMPTS_COUNT = 10

    # Remove torrents with too much attempts count (ignore after "MAX_ATTEMPTS_COUNT" attempts)
    db.torrents.remove({"$and": [{"name": {"$exists": False}},
                                 {"files": {"$exists": False}},
                                 {"attempt": {"$gte": MAX_ATTEMPTS_COUNT}}]}
                       )

    # Find candidates to load
    if torrents:
        torrents_list = torrents
    else:
        torrents_list = list(
            db.torrents.find({"$and": [{"name": {"$exists": False}},
                                       {"files": {"$exists": False}},
                                       {"$or": [{"attempt": {"$exists": False}},
                                                {"attempt": {"$lt": MAX_ATTEMPTS_COUNT}}
                                                ]}
                                       ]}
                             )
        )
        shuffle(torrents_list)

    if torrents_list:
        item = torrents_list[0]
        info_hash = item["info_hash"]

        # Increase torrent attempts count
        db.torrents.update({"info_hash": info_hash},
                           {"$set": {"attempt": item.get("attempt", 0) + 1}})

        info_hash = unhexlify(info_hash)
    else:
        info_hash = None

    try_load_metadata(
        info_hash=info_hash,
        schedule=60,  # Wait 60 seconds
        on_torrent_loaded=lambda metadata: __store_metadata(db, metadata, try_load_metadata),
        on_torrent_not_found=lambda: __index_next_info_hash(db, try_load_metadata, torrents_list[1:])
    )


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
