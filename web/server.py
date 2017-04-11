from pymongo import MongoClient, DESCENDING

from flask import Flask, redirect, abort
from flask import render_template
from flask import request

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


def start_server(mongodb_uri, host, port):
    mongo_client = MongoClient(mongodb_uri)
    try:
        db = mongo_client.grapefruit

        # Create this index manually:
        # db.torrents.createIndex({"$**": "text"})

        app = Flask(__name__, static_url_path="")

        results_per_page = 10

        @app.route("/")
        def show_index():
            return render_template("index.html", torrents_count=db.torrents.count())

        def render_results(source_url, query, page, elapsed_time, results):
            items = list(results)

            arguments = {
                "source_url": source_url,
                "query": query,
                "page": page,
                "total_pages": len(items) / results_per_page + 1,
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
                start_time = time()
                # Query database
                results = db.torrents.find(
                    {"$text": {"$search": query}},
                    {"score": {"$meta": "textScore"}}
                ).sort([("score", {"$meta": "textScore"})])

                elapsed_time = time() - start_time

                return render_results("/search", query, page, elapsed_time, results)
            else:
                return redirect("/")

        @app.route("/latest")
        def latest():
            page = max(int(request.args.get("p", default=1)), 1)

            start_time = time()
            # Query database
            results = db.torrents.find().sort("_id", DESCENDING).limit(100)

            elapsed_time = time() - start_time

            return render_results("/latest", "", page, elapsed_time, results)

        @app.route("/details")
        def details():
            query = request.args.get("q")
            info_hash = request.args.get("t")

            if info_hash:
                # Query database
                result = db.torrents.find_one({"info_hash": info_hash})

                if result is not None:
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

        app.run(host=host, port=port)
    finally:
        mongo_client.close()
