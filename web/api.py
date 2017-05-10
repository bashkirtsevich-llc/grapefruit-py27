from time import time

from pymongo import DESCENDING


def db_search_torrents(db, db_lock, query, fields, offset=0, limit=0):
    assert isinstance(fields, list)

    projection = {"score": {"$meta": "textScore"}, "_id": False}

    for field in fields:
        projection[field] = True

    start_time = time()

    # Query database
    with db_lock:
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


def db_get_torrent_details(db, db_lock, info_hash):
    start_time = time()

    # Query database
    with db_lock:
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


def db_get_last_torrents(db, db_lock, fields, offset=0, limit=100):
    assert isinstance(fields, list)

    projection = {"_id": False}

    for field in fields:
        projection[field] = True

    start_time = time()

    # Query database
    with db_lock:
        cursor = db.torrents.find(
            filter={"$and": [
                {"name": {"$exists": True}},
                {"files": {"$exists": True}}]},
            projection=projection,
            sort=[("_id", DESCENDING)]
        )

    if cursor:
        results_count, results = min(cursor.count(), 100), list(cursor.skip(offset).limit(limit))
    else:
        results_count, results = 0, []

    elapsed_time = time() - start_time

    return results_count, results, elapsed_time