from time import time

from pymongo import DESCENDING


def db_search_torrents(db, query, fields, offset=0, limit=0):
    assert isinstance(fields, list)

    projection = {"score": {"$meta": "textScore"}, "_id": False}

    for field in fields:
        projection[field] = True

    start_time = time()

    cursor = db.torrents.find(
        filter={"$text": {"$search": query}},
        projection=projection,
        sort=[("score", {"$meta": "textScore"}), ("timestamp", DESCENDING)]
    )

    if cursor:
        results_count, results = cursor.count(), list(cursor.skip(offset).limit(limit))
    else:
        results_count, results = 0, []

    elapsed_time = time() - start_time

    return results_count, results, elapsed_time


def db_get_torrent_details(db, info_hash):
    start_time = time()

    # Query database
    result = db.torrents.find_one(
        filter={"info_hash": info_hash},
        projection={
            "_id": False,
            "name": True,
            "files": True,
            "info_hash": True
        }
    )

    elapsed_time = time() - start_time

    return result, elapsed_time


def db_get_last_torrents(db, fields, offset=0, limit=100):
    assert isinstance(fields, list)

    projection = {"_id": False}
    projection.update({field: True for field in fields})

    start_time = time()

    # Query database
    cursor = db.torrents.find(
        filter={},
        projection=projection,
        sort=[("timestamp", DESCENDING)]
    )

    if cursor:
        results_count, results = min(cursor.count(), 100), list(cursor.skip(offset).limit(limit))
    else:
        results_count, results = 0, []

    elapsed_time = time() - start_time

    return results_count, results, elapsed_time


def db_get_torrents_count(db):
    return db.torrents.count()


def db_get_hashes_count(db):
    return db.hashes.count()


def db_torrent_exists(db, info_hash, has_metadata=False):
    coll = db.torrents if has_metadata else db.hashes
    return coll.count(filter={"info_hash": info_hash}) > 0


def db_insert_or_update_torrent(db, db_lock, info_hash, timestamp, metadata=None):
    with db_lock:
        result = False

        if not db_torrent_exists(db, info_hash, False):
            db.hashes.insert_one({"info_hash": info_hash,
                                  "access_count": 0,
                                  "loaded": bool(metadata)})
            result = True

        if metadata and not db_torrent_exists(db, info_hash, True):
            db.torrents.insert_one(dict({"info_hash": info_hash,
                                         "timestamp": timestamp},
                                        **metadata))
            db.hashes.update({"info_hash": info_hash},
                             {"$set": {"loaded": True}})
            result = True

        return result


def db_increase_access_count(db, db_lock, info_hashes):
    with db_lock:
        for info_hash in info_hashes:
            db.hashes.update(
                {"info_hash": info_hash},
                {"$inc": {"access_count": 1}}
            )


def db_fetch_not_indexed_torrents(db, size=10, max_access_count=3):
    def make_query(is_lt):
        return [
            {"$match": {
                "loaded": False,
                "access_count": {"$lt" if is_lt else "$gte": max_access_count}}},
            {"$sample": {"size": size}}
        ]

    def select(query):
        return map(lambda item: item["info_hash"], db.hashes.aggregate(query))

    result = select(make_query(True)) + select(make_query(False))
    return result[:size]


def db_load_routing_table(db, db_lock, local_node_host, local_node_port, local_node_id=None):
    with db_lock:
        cond_list = [{"local_node_host": local_node_host},
                     {"local_node_port": local_node_port}]

        if local_node_id:
            cond_list.append({"local_node_id": local_node_id})

        return db.crawler_route.find_one(
            filter={"$and": cond_list},
            projection={"_id": False,
                        "local_node_host": True,
                        "buckets": True,
                        "local_node_id": True,
                        "local_node_port": True})


def db_store_routing_table(db, db_lock, buckets, node_id, node_host, node_port):
    with db_lock:
        if db.crawler_route.count({"local_node_id": node_id}) > 0:
            db.crawler_route.update({"local_node_id": node_id},
                                    {"$set": {"buckets": buckets}})
        else:
            db.crawler_route.insert({
                "buckets": buckets,
                "local_node_id": node_id,
                "local_node_host": node_host,
                "local_node_port": node_port
            })
