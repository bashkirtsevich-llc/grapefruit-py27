from __future__ import division
import urllib
import math

from threading import Lock

from flask import Flask
from flask import redirect
from flask import abort
from flask import jsonify
from flask import render_template
from flask import request

from markupsafe import Markup

from pymongo import MongoClient, TEXT, ASCENDING

from utils import *
from api import *

from datetime import datetime


def start_server(mongodb_uri, host, port, api_access_host=None):
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

        results_per_page = 10

        @app.template_filter('urlencode')
        def urlencode_filter(s):
            if type(s) == 'Markup':
                s = s.unescape()
            s = s.encode('utf8')
            s = urllib.quote_plus(s)
            return Markup(s)

        # Error pages responding
        @app.errorhandler(403)
        def page_not_found(e):
            return render_template("error.html", error_code=403), 403

        @app.errorhandler(404)
        def page_not_found(e):
            return render_template("error.html", error_code=404), 404

        @app.errorhandler(500)
        def internal_server_error(e):
            return render_template("error.html", error_code=500), 500

        # WEB-server API methods
        @app.route("/api/search")
        def api_search():
            if request.remote_addr == api_access_host:
                query = request.args.get("query")
                offset = abs(int(request.args.get("offset", default=0)))
                limit = min(abs(int(request.args.get("limit", default=100))), 100)

                if query:
                    results_count, results, elapsed_time = db_search_torrents(
                        db, db_lock,
                        query=query,
                        fields=["name", "info_hash"],
                        offset=offset,
                        limit=limit
                    )
                    return jsonify({"result": results, "count": results_count, "elapsed_time": elapsed_time})
                else:
                    return jsonify({"result": {"code": 404, "message": "empty \"query\" argument"}})
            else:
                abort(403)

        @app.route("/api/latest")
        def api_latest():
            if request.remote_addr == api_access_host:
                offset = abs(int(request.args.get("offset", default=0)))
                limit = min(abs(int(request.args.get("limit", default=100))), 100)

                results_count, results, elapsed_time = db_get_last_torrents(
                    db, db_lock,
                    fields=["name", "info_hash"],
                    offset=offset,
                    limit=limit
                )
                total_count = db_get_torrents_count(db, db_lock)

                return jsonify({"result": results, "count": results_count, "total_count": total_count,
                                "elapsed_time": elapsed_time})
            else:
                abort(403)

        @app.route("/api/details")
        def api_details():
            if request.remote_addr == api_access_host:
                info_hash = request.args.get("info_hash", None)
                if info_hash:
                    result, elapsed_time = db_get_torrent_details(db, db_lock, info_hash)
                    return jsonify({"result": result, "elapsed_time": elapsed_time})
                else:
                    return jsonify({"result": {"code": 500, "message": "missed \"info_hash\" argument"}})
            else:
                abort(403)

        @app.route("/api/add_torrent", methods=['POST'])
        def api_add_torrent():
            if request.remote_addr == api_access_host:
                info_hash = request.form.get("info_hash", None)
                metadata = request.form.get("metadata", None)

                if info_hash:
                    timestamp = datetime.utcnow()

                    try:
                        if db_torrent_exists(db, db_lock, info_hash, metadata is not None):
                            return jsonify({"result": {"code": 409, "message": "already exists"}})
                        elif metadata:
                            if metadata.get("info_hash", info_hash) == info_hash:
                                md = {"timestamp": timestamp}
                                md.update(metadata)

                                db_insert_or_update_torrent(db, db_lock, info_hash, md)
                                return jsonify({"result": {"code": 200, "message": "OK"}})
                            else:
                                return jsonify({"result": {
                                    "code": 500, "message": "invalid extra field \"info_hash\" in \"metadata\""
                                }})
                        else:
                            db_insert_or_update_torrent(db, db_lock, info_hash)
                    finally:
                        # Write info_hash into log ("db.hashes") collection
                        db_log_info_hash(db, db_lock, info_hash, timestamp)
                else:
                    return jsonify({"result": {"code": 500, "message": "missed \"info_hash\" argument"}})
            else:
                abort(403)

        @app.route("/api/fetch_torrents_for_load")
        def api_fetch_torrents_for_load():
            if request.remote_addr == api_access_host:
                limit = request.form.get("limit", 10)
                max_access_count = request.form.get("max_access_count", 3)
                inc_access_count = request.form.get("inc_access_count", False)

                result = db_fetch_not_indexed_torrents(db, db_lock, limit, max_access_count)

                if inc_access_count:
                    db_increase_access_count(db, db_lock, result)

                return jsonify({"result": result})
            else:
                abort(403)

        @app.route("/api/load_routing_table")
        def api_load_routing_table():
            if request.remote_addr == api_access_host:
                local_node_host = request.form.get("local_node_host", None)
                local_node_port = request.form.get("local_node_port", None)
                local_node_id = request.form.get("local_node_id", None)

                if local_node_host and local_node_port:
                    result = db_load_routing_table(db, db_lock, local_node_host, local_node_port, local_node_id)

                    if result:
                        return jsonify({"result": result})
                    else:
                        return jsonify({"result": {"code": 404, "message": "not found"}})
                else:
                    return jsonify({"result": {
                        "code": 500,
                        "message": "missed one of this arguments: \"local_node_host\", \"local_node_port\""}
                    })
            else:
                abort(403)

        @app.route("/api/store_routing_table")
        def api_store_routing_table():
            if request.remote_addr == api_access_host:
                buckets = request.form.get("buckets", None)
                local_node_id = request.form.get("local_node_id", None)
                local_node_host = request.form.get("local_node_host", None)
                local_node_port = request.form.get("local_node_port", None)

                if buckets and local_node_id and local_node_host and local_node_port:
                    db_store_routing_table(db, db_lock, buckets, local_node_id, local_node_host, local_node_port)
                    return jsonify({"result": {"code": 200, "message": "OK"}})
                else:
                    return jsonify({"result": {
                        "code": 500,
                        "message": "missed one of this arguments: \"buckets\", \"local_node_id\", \"local_node_host\", \"local_node_port\""}
                    })
            else:
                abort(403)

        # Regular http requests
        @app.route("/")
        def show_index():
            return render_template("index.html",
                                   torrents_count=db_get_torrents_count(db, db_lock))

        def render_results(source_url, query, page, results, results_count, elapsed_time):
            items = list(results)

            arguments = {
                "source_url": source_url,
                "query": query,
                "page": page,
                "total_pages": int(math.ceil(results_count / results_per_page)),
                "total_count": results_count,
                "time_elapsed": round(elapsed_time, 3),
                "results": map(lambda item: {
                    "info_hash": item["info_hash"],
                    "title": item["name"],
                    "size": get_files_size(item["files"]),
                    "files": get_files_list(item["files"], first_ten=True),
                    "files_count": len(item["files"])
                }, items)
            }

            return render_template("results.html", **arguments)

        @app.route("/search")
        def search():
            query = request.args.get("q")
            page = max(int(request.args.get("p", default=1)), 1)

            if query:
                results_count, results, elapsed_time = db_search_torrents(
                    db, db_lock,
                    query=query,
                    fields=["name", "files", "info_hash"],
                    limit=results_per_page,
                    offset=(page - 1) * results_per_page
                )
                return render_results("/search", query, page, results, results_count, elapsed_time)
            else:
                return redirect("/")

        @app.route("/latest")
        def latest():
            page = max(int(request.args.get("p", default=1)), 1)

            results_count, results, elapsed_time = db_get_last_torrents(
                db, db_lock,
                fields=["name", "files", "info_hash"],
                limit=results_per_page,
                offset=(page - 1) * results_per_page
            )

            return render_results("/latest", "", page, results, min(results_count, 100), elapsed_time)

        @app.route("/details")
        def details():
            query = request.args.get("q")
            info_hash = request.args.get("t")

            if info_hash:
                result, _ = db_get_torrent_details(db, db_lock, info_hash)

                if result:
                    arguments = {
                        "query": query,
                        "title": result["name"],
                        "size": get_files_size(result["files"]),
                        "info_hash": result["info_hash"],
                        "files": get_files_list(result["files"])
                    }

                    return render_template("details.html", **arguments)
                else:
                    abort(404)
            else:
                return redirect("/")

        app.run(host=host, port=port, threaded=True)
    finally:
        mongo_client.close()
