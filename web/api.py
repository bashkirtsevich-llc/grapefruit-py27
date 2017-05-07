from time import time

from pymongo import DESCENDING


def db_search_torrents(db, db_lock, query, fields):
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
        results = list(cursor)
    else:
        results = []

    elapsed_time = time() - start_time

    return results, elapsed_time


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


def db_get_last_torrents(db, db_lock, fields, limit=100):
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
            sort=[("_id", DESCENDING)],
            limit=limit
        )

    if cursor:
        results = list(cursor)
    else:
        results = []

    elapsed_time = time() - start_time

    return results, elapsed_time
