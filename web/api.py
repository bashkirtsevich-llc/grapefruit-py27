from time import time
from random import randrange

from pymongo import DESCENDING


def db_search_torrents(db, query, fields, offset=0, limit=0):
    assert isinstance(fields, list)

    projection = {"score": {"$meta": "textScore"}, "_id": False}

    for field in fields:
        projection[field] = True

    start_time = time()

    # Query database
    cursor = db.torrents.find(
        filter={"$and": [
            {"$text": {"$search": query}},
            {"name": {"$exists": True}},
            {"files": {"$exists": True}}]},
        projection=projection,
        sort=[("score", {"$meta": "textScore"})]
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
        filter={"$and": [
            {"info_hash": info_hash},
            {"name": {"$exists": True}},
            {"files": {"$exists": True}}]},
        projection={"_id": False,
                    "name": True,
                    "files": True,
                    "info_hash": True}
    )

    elapsed_time = time() - start_time

    return result, elapsed_time


def db_get_last_torrents(db, fields, offset=0, limit=100):
    assert isinstance(fields, list)

    projection = {"_id": False}

    for field in fields:
        projection[field] = True

    start_time = time()

    # Query database
    cursor = db.torrents.find(
        filter={"$and": [
            {"name": {"$exists": True}},
            {"files": {"$exists": True}}]},
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
    return db.torrents.count(
        filter={"$and": [
            {"name": {"$exists": True}},
            {"files": {"$exists": True}}]}
    )


def db_torrent_exists(db, info_hash, has_metadata=False):
    cond = [{"info_hash": info_hash}]

    if has_metadata:
        cond.extend([{"name": {"$exists": True}},
                     {"files": {"$exists": True}}])

    return db.torrents.count(
        filter={"$and": cond}
    ) > 0


def db_insert_or_update_torrent(db, db_lock, info_hash, metadata=None):
    with db_lock:
        if metadata and db_torrent_exists(db, info_hash, True):
            return False
        else:
            document = {"info_hash": info_hash}

            if metadata:
                document.update(metadata)

            if db_torrent_exists(db, info_hash):
                db.torrents.update({"info_hash": info_hash}, {"$set": metadata})
            else:
                db.torrents.insert_one(document)

            return True


def db_log_info_hash(db, info_hash, timestamp):
    db.hashes.insert({
        "info_hash": info_hash,
        "timestamp": timestamp
    })


def db_increase_access_count(db, db_lock, info_hashes):
    with db_lock:
        for info_hash in info_hashes:
            db.torrents.update(
                {"info_hash": info_hash},
                {"$inc": {"access_count": 1}}
            )


def db_fetch_not_indexed_torrents(db, db_lock, limit=10, max_access_count=3):
    def make_query(lt):
        return {"$and": [
            {"name": {"$exists": False}},
            {"files": {"$exists": False}},
            {"$or": [
                {"access_count": {"$exists": False}},
                {"access_count": {"$lt" if lt else "$gte": max_access_count}}
            ]}
        ]}

    def select(query, fetch_limit):
        # Find candidates to load
        cursor = db.torrents.find(
            filter=query,
            projection={"_id": False,
                        "info_hash": True}
        )

        if cursor:
            return map(
                lambda item: item["info_hash"],
                cursor.skip(randrange(max(cursor.count() - fetch_limit, 1))).limit(fetch_limit)
            )
        else:
            return []

    with db_lock:
        result = []

        result.extend(select(make_query(True), limit))
        if len(result) < limit:
            result.extend(select(make_query(False), limit - len(result)))

        return result


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
