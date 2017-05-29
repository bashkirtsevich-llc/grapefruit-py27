from binascii import unhexlify
from pymongo import MongoClient
from torrent import load_torrent
from random import shuffle, randrange


def __store_metadata(db, metadata, *args, **kwargs):
    try:
        key = {"info_hash": metadata["info_hash"]}

        value = {"name": metadata["name"],
                 "files": map(lambda f: {"path": f["path"],
                                         "length": f["length"]},
                              metadata["files"])}

        db.torrents.update(key, {"$set": value,
                                 "$unset": {"attempt": ""}})
    finally:
        __index_next_info_hash(db, *args, **kwargs)


def __get_hash_iterator(db):
    # This method return fetch method, who will reload torrent list, when he is empty
    def load_torrents():
        MAX_ATTEMPTS_COUNT = 10
        FETCH_LIMIT = 10

        # Remove torrents with too much attempts count (ignore after "MAX_ATTEMPTS_COUNT" attempts)
        db.torrents.remove(
            {"$and": [
                {"name": {"$exists": False}},
                {"files": {"$exists": False}},
                {"attempt": {"$gte": MAX_ATTEMPTS_COUNT}}
            ]}
        )

        # Find candidates to load
        cursor = db.torrents.find(
            {"$and": [
                {"name": {"$exists": False}},
                {"files": {"$exists": False}},
                {"$or": [
                    {"attempt": {"$exists": False}},
                    {"attempt": {"$lt": MAX_ATTEMPTS_COUNT}}
                ]}
            ]}
        )

        if cursor:
            return list(
                cursor.skip(
                    randrange(max(cursor.count() - FETCH_LIMIT, 1))
                ).limit(FETCH_LIMIT)
            )
        else:
            return []

    # Local torrent items storage, using for closure from fetch_next_item
    torrents = []

    def fetch_next_item():
        if not torrents:
            torrents.extend(load_torrents())

        if torrents:
            return torrents.pop(0)
        else:
            return None

    return fetch_next_item


def __index_next_info_hash(db, try_load_metadata, get_next_torrent):
    item = get_next_torrent()
    if item:
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
        on_torrent_loaded=lambda metadata: __store_metadata(db, metadata, try_load_metadata, get_next_torrent),
        on_torrent_not_found=lambda: __index_next_info_hash(db, try_load_metadata, get_next_torrent)
    )


def __index_torrents(db, try_load_metadata):
    iterator = __get_hash_iterator(db)

    for _ in xrange(10):
        __index_next_info_hash(db, try_load_metadata, iterator)


def start_indexer(mongodb_uri, port, node_id=None, bootstrap_node_address=("router.bittorrent.com", 6881)):
    mongodb_client = MongoClient(mongodb_uri)
    try:
        db = mongodb_client.grapefruit

        load_torrent(bootstrap_node_address, port,
                     node_id=node_id,
                     on_bootstrap_done=lambda try_load_metadata: __index_torrents(db, try_load_metadata))
    finally:
        mongodb_client.close()
