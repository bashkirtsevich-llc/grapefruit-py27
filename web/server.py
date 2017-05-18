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

from pymongo import MongoClient, TEXT

from utils import get_files_list
from utils import get_files_size

from api import db_search_torrents
from api import db_get_torrent_details
from api import db_get_last_torrents


def start_server(mongodb_uri, host, port, api_access_host=None):
    mongo_client = MongoClient(mongodb_uri)
    try:
        db = mongo_client.grapefruit

        db_lock = Lock()

        if "$**_text" not in db.torrents.index_information():
            db.torrents.create_index([("$**", TEXT)],
                                     name="$**_text",
                                     weights={"name": 3, "path": 2},
                                     default_language="english")

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
                return jsonify({"result": results, "count": results_count, "elapsed_time": elapsed_time})
            else:
                abort(403)

        @app.route("/api/details")
        def api_details():
            if request.remote_addr == api_access_host:
                info_hash = request.args.get("info_hash")
                if info_hash:
                    result, elapsed_time = db_get_torrent_details(db, db_lock, info_hash)
                    return jsonify({"result": result, "elapsed_time": elapsed_time})
                else:
                    return jsonify({"result": {"code": 404, "message": "empty \"info_hash\" argument"}})
            else:
                abort(403)

        # Regular http requests

        @app.route("/")
        def show_index():
            return render_template("index.html",
                                   torrents_count=db.torrents.find(
                                       {"$and": [
                                           {"name": {"$exists": True}},
                                           {"files": {"$exists": True}}]}
                                   ).count())

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
