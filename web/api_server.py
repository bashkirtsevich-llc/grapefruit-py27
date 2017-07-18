import logging
import os

import json

from threading import Lock

from flask import Flask
from flask import jsonify
from flask import request
from flask_pymongo import PyMongo

from schema import deploy_schema

from api import *

from datetime import datetime


def start_api_server(mongodb_uri, host, port):
    logging.basicConfig(filename=os.devnull,
                        level=logging.DEBUG)

    deploy_schema(mongodb_uri)

    app = Flask(__name__, static_url_path="")
    app.config["MONGO_URI"] = mongodb_uri

    mongo = PyMongo(app)
    db_lock = Lock()

    @app.route("/api/search")
    def api_search():
        query = request.args.get("query")
        offset = abs(int(request.args.get("offset", default=0)))
        limit = min(abs(int(request.args.get("limit", default=100))), 100)

        if query:
            results_count, results, elapsed_time = db_search_torrents(
                mongo.db,
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
            mongo.db,
            fields=["name", "info_hash"],
            offset=offset,
            limit=limit
        )
        total_count = db_get_torrents_count(mongo.db)

        return jsonify({"result": results, "count": results_count, "total_count": total_count,
                        "elapsed_time": elapsed_time})

    @app.route("/api/details")
    def api_details():
        info_hash = request.args.get("info_hash", None)
        if info_hash:
            result, elapsed_time = db_get_torrent_details(mongo.db, info_hash)
            return jsonify({"result": result, "elapsed_time": elapsed_time})
        else:
            return jsonify({"result": {"code": 500, "message": "missed \"info_hash\" argument"}})

    @app.route("/api/add_torrent", methods=['POST'])
    def api_add_torrent():
        info_hash = request.form.get("info_hash", default=None, type=str)
        metadata = json.loads(request.form.get("metadata", default="{}", type=str), encoding="utf-8")

        if info_hash:
            if metadata and metadata.get("info_hash", info_hash) != info_hash:
                return jsonify({"result": {
                    "code": 500, "message": "invalid extra field \"info_hash\" in \"metadata\""
                }})

            if db_insert_or_update_torrent(mongo.db, db_lock, info_hash, datetime.utcnow(), metadata):
                return jsonify({"result": {"code": 202, "message": "accepted"}})
            else:
                return jsonify({"result": {"code": 409, "message": "already exists"}})
        else:
            return jsonify({"result": {"code": 500, "message": "missed \"info_hash\" argument"}})

    @app.route("/api/fetch_torrents_for_load")
    def api_fetch_torrents_for_load():
        limit = request.args.get("limit", default=10, type=int)
        max_access_count = request.args.get("max_access_count", default=3, type=int)
        inc_access_count = request.args.get(
            "inc_access_count", default="false", type=str).lower() == "true"

        result = db_fetch_not_indexed_torrents(mongo.db, limit, max_access_count)

        if inc_access_count:
            db_increase_access_count(mongo.db, db_lock, result)

        return jsonify({"result": result})

    @app.route("/api/load_routing_table")
    def api_load_routing_table():
        local_node_host = request.args.get("local_node_host", default=None, type=str)
        local_node_port = request.args.get("local_node_port", default=0, type=int)
        local_node_id = request.args.get("local_node_id", default=None, type=str)

        if local_node_host and local_node_port:
            result = db_load_routing_table(mongo.db, db_lock, local_node_host, local_node_port,
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
            db_store_routing_table(mongo.db, db_lock, buckets, local_node_id, local_node_host,
                                   local_node_port)
            return jsonify({"result": {"code": 200, "message": "OK"}})
        else:
            return jsonify({"result": {
                "code": 500,
                "message": "missed one of this arguments: \"buckets\", \"local_node_id\", \"local_node_host\", \"local_node_port\""}
            })

    app.run(host=host, port=port, threaded=True)
