import logging
import os

import json

from threading import Lock

from flask import Flask
from flask import jsonify
from flask import request

from pymongo import MongoClient, TEXT, ASCENDING

from api import *

from datetime import datetime


def start_api_server(mongodb_uri, host, port):
    logging.basicConfig(filename=os.devnull,
                        level=logging.DEBUG)

    mongo_client = MongoClient(mongodb_uri)
    try:
        db = mongo_client.grapefruit
        db_lock = Lock()

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

        torrents = db.torrents
        torrents_indexes = torrents.index_information()

        for index_info in ({"name": "fulltext_index", "keys": [("$**", TEXT)], "weights": {"name": 3, "path": 2},
                            "default_language": "english"},
                           {"name": "info_hash", "keys": [("info_hash", ASCENDING)], "unique": True},
                           {"name": "access_count", "keys": [("access_count", ASCENDING)]},
                           {"name": "timestamp", "keys": [("timestamp", DESCENDING)]}):
            if index_info["name"] not in torrents_indexes:
                torrents.create_index(**index_info)

        app = Flask(__name__, static_url_path="")

        @app.route("/api/search")
        def api_search():
            query = request.args.get("query")
            offset = abs(int(request.args.get("offset", default=0)))
            limit = min(abs(int(request.args.get("limit", default=100))), 100)

            if query:
                results_count, results, elapsed_time = db_search_torrents(
                    db,
                    query=query,
                    fields=["name", "info_hash"],
                    offset=offset,
                    limit=limit
                )
                return jsonify({"result": results, "count": results_count, "elapsed_time": elapsed_time})
            else:
                return jsonify({"result": {"code": 404, "message": "empty \"query\" argument"}})

        @app.route("/api/latest")
        def api_latest():
            offset = abs(int(request.args.get("offset", default=0)))
            limit = min(abs(int(request.args.get("limit", default=100))), 100)

            results_count, results, elapsed_time = db_get_last_torrents(
                db,
                fields=["name", "info_hash"],
                offset=offset,
                limit=limit
            )
            total_count = db_get_torrents_count(db)

            return jsonify({"result": results, "count": results_count, "total_count": total_count,
                            "elapsed_time": elapsed_time})

        @app.route("/api/details")
        def api_details():
            info_hash = request.args.get("info_hash", None)
            if info_hash:
                result, elapsed_time = db_get_torrent_details(db, info_hash)
                return jsonify({"result": result, "elapsed_time": elapsed_time})
            else:
                return jsonify({"result": {"code": 500, "message": "missed \"info_hash\" argument"}})

        @app.route("/api/add_torrent", methods=['POST'])
        def api_add_torrent():
            info_hash = request.form.get("info_hash", default=None, type=str)
            metadata = json.loads(request.form.get("metadata", default="{}", type=str), encoding="utf-8")

            if info_hash:
                timestamp = datetime.utcnow()
                try:
                    md = {"timestamp": timestamp}

                    if metadata:
                        if metadata.get("info_hash", info_hash) == info_hash:
                            md.update(metadata)
                        else:
                            return jsonify({"result": {
                                "code": 500, "message": "invalid extra field \"info_hash\" in \"metadata\""
                            }})

                    if db_insert_or_update_torrent(db, db_lock, info_hash, md):
                        return jsonify({"result": {"code": 202, "message": "accepted"}})
                    else:
                        return jsonify({"result": {"code": 409, "message": "already exists"}})
                finally:
                    # Metadata not presented, when function called from crawler
                    if not metadata:
                        db_log_info_hash(db, info_hash, timestamp)
            else:
                return jsonify({"result": {"code": 500, "message": "missed \"info_hash\" argument"}})

        @app.route("/api/fetch_torrents_for_load")
        def api_fetch_torrents_for_load():
            limit = request.args.get("limit", default=10, type=int)
            max_access_count = request.args.get("max_access_count", default=3, type=int)
            inc_access_count = request.args.get(
                "inc_access_count", default="false", type=str).lower() == "true"

            result = db_fetch_not_indexed_torrents(db, db_lock, limit, max_access_count)

            if inc_access_count:
                db_increase_access_count(db, db_lock, result)

            return jsonify({"result": result})

        @app.route("/api/load_routing_table")
        def api_load_routing_table():
            local_node_host = request.args.get("local_node_host", default=None, type=str)
            local_node_port = request.args.get("local_node_port", default=0, type=int)
            local_node_id = request.args.get("local_node_id", default=None, type=str)

            if local_node_host and local_node_port:
                result = db_load_routing_table(db, db_lock, local_node_host, local_node_port,
                                               local_node_id)

                if result:
                    return jsonify({"result": result})
                else:
                    return jsonify({"result": {"code": 404, "message": "not found"}})
            else:
                return jsonify({"result": {
                    "code": 500,
                    "message": "missed one of this arguments: \"local_node_host\", \"local_node_port\""}
                })

        @app.route("/api/store_routing_table", methods=['POST'])
        def api_store_routing_table():
            buckets = json.loads(request.form.get("buckets", default="{}", type=str))
            local_node_id = request.form.get("local_node_id", default=None, type=str)
            local_node_host = request.form.get("local_node_host", default=None, type=str)
            local_node_port = request.form.get("local_node_port", default=None, type=int)

            if buckets and local_node_id and local_node_host and local_node_port:
                db_store_routing_table(db, db_lock, buckets, local_node_id, local_node_host,
                                       local_node_port)
                return jsonify({"result": {"code": 200, "message": "OK"}})
            else:
                return jsonify({"result": {
                    "code": 500,
                    "message": "missed one of this arguments: \"buckets\", \"local_node_id\", \"local_node_host\", \"local_node_port\""}
                })

        app.run(host=host, port=port, threaded=True)
    finally:
        mongo_client.close()
