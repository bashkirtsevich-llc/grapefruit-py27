from pymongo import MongoClient, TEXT, ASCENDING, DESCENDING


def deploy_schema(mongodb_uri):
    mongo_client = MongoClient(mongodb_uri)
    try:
        db = mongo_client.grapefruit

        for coll_name in ["crawler_route", "hashes", "torrents"]:
            if coll_name not in db.collection_names():
                db.create_collection(coll_name)

        # Index by local node info for crawler_route
        if "host_port_id" not in db.crawler_route.index_information():
            db.crawler_route.create_index(keys=[("local_node_host", ASCENDING),
                                                ("local_node_port", ASCENDING),
                                                ("local_node_id", ASCENDING)],
                                          name="host_port_id",
                                          unique=True)

        # Pump "hashes" collection
        hashes = db.hashes
        hashes_indexes = hashes.index_information()

        for index_info in ({"name": "info_hash", "keys": [("info_hash", ASCENDING)], "unique": True},
                           {"name": "loaded", "keys": [("loaded", ASCENDING)]}):
            if index_info["name"] not in hashes_indexes:
                hashes.create_index(**index_info)

        # Pump "torrents" collection
        torrents = db.torrents
        torrents_indexes = torrents.index_information()

        for index_info in ({"name": "fulltext", "keys": [("name", TEXT),
                                                         ("info_hash", TEXT),
                                                         ("files.path", TEXT)],
                            "weights": {"name": 99999, "info_hash": 99999, "files.path": 1},
                            "default_language": "english"},
                           {"name": "info_hash", "keys": [("info_hash", ASCENDING)], "unique": True},
                           {"name": "access_count", "keys": [("access_count", ASCENDING)]},
                           {"name": "timestamp", "keys": [("timestamp", DESCENDING)]}):
            if index_info["name"] not in torrents_indexes:
                torrents.create_index(**index_info)
    finally:
        mongo_client.close()
