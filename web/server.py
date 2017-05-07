from pymongo import MongoClient, DESCENDING, TEXT

from threading import Lock

from flask import Flask, redirect, abort
from flask import render_template
from flask import request
from flask import jsonify

import urllib
from markupsafe import Markup

from time import time


def __sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)

        num /= 1024.0

    return "%.1f %s%s" % (num, "Y", suffix)


def __get_files_list(files, first_ten=False):
    return map(lambda f: {"name": reduce(lambda r, e: r + ("/" if r else "") + e, f["path"], ""),
                          "size": __sizeof_fmt(f["length"])}, files[:10] if first_ten else files)


def __get_files_size(files):
    return __sizeof_fmt(reduce(lambda r, e: r + e["length"], files, 0))


# INTERNAL API
def __db_search_torrents(db, db_lock, query, fields):
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


def __db_get_torrent_details(db, db_lock, info_hash):
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


def __db_get_last_torrents(db, db_lock, fields, limit=100):
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


# END OF INTERNAL API


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
                if query:
                    results, elapsed_time = __db_search_torrents(
                        db, db_lock,
                        query=query,
                        fields=["name", "info_hash"]
                    )
                    return jsonify({"result": results, "elapsed_time": elapsed_time})
                else:
                    return jsonify({"result": {"code": 404, "message": "empty \"query\" argument"}})
            else:
                abort(403)

        @app.route("/api/details")
        def api_details():
            if request.remote_addr == api_access_host:
                info_hash = request.args.get("info_hash")
                if info_hash:
                    result, elapsed_time = __db_get_torrent_details(db, db_lock, info_hash)
                    return jsonify({"result": result, "elapsed_time": elapsed_time})
                else:
                    return jsonify({"result": {"code": 404, "message": "empty \"info_hash\" argument"}})
            else:
                abort(403)

        @app.route("/api/latest")
        def api_latest():
            if request.remote_addr == api_access_host:
                limit = min(int(request.args.get("limit", default=1)), 100)
                result, elapsed_time = __db_get_last_torrents(
                    db, db_lock,
                    fields=["name", "info_hash"],
                    limit=limit
                )
                return jsonify({"result": result, "elapsed_time": elapsed_time})
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

        def render_results(source_url, query, page, results, elapsed_time):
            items = list(results)

            arguments = {
                "source_url": source_url,
                "query": query,
                "page": page,
                "total_pages": len(items) / results_per_page + (1 if len(items) % results_per_page != 0 else 0),
                "total_count": len(items),
                "time_elapsed": round(elapsed_time, 3),
                "results": map(lambda item: {
                    "info_hash": item["info_hash"],
                    "title": item["name"],
                    "size": __get_files_size(item["files"]),
                    "files": __get_files_list(item["files"], first_ten=True),
                    "files_count": len(item["files"])
                }, items[(page - 1) * results_per_page: (page - 1) * results_per_page + results_per_page])
            }

            return render_template("results.html", **arguments)

        @app.route("/search")
        def search():
            query = request.args.get("q")
            page = max(int(request.args.get("p", default=1)), 1)

            if query:
                results, elapsed_time = __db_search_torrents(
                    db, db_lock,
                    query=query,
                    fields=["name", "files", "info_hash"]
                )
                return render_results("/search", query, page, results, elapsed_time)
            else:
                return redirect("/")

        @app.route("/latest")
        def latest():
            page = max(int(request.args.get("p", default=1)), 1)

            results, elapsed_time = __db_get_last_torrents(
                db, db_lock,
                fields=["name", "files", "info_hash"]
            )

            return render_results("/latest", "", page, results, elapsed_time)

        @app.route("/details")
        def details():
            query = request.args.get("q")
            info_hash = request.args.get("t")

            if info_hash:
                result, _ = __db_get_torrent_details(db, db_lock, info_hash)

                if result:
                    arguments = {
                        "query": query,
                        "title": result["name"],
                        "size": __get_files_size(result["files"]),
                        "info_hash": result["info_hash"],
                        "files": __get_files_list(result["files"])
                    }

                    return render_template("details.html", **arguments)
                else:
                    abort(404)
            else:
                return redirect("/")

        app.run(host=host, port=port, threaded=True)
    finally:
        mongo_client.close()
