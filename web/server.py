from pymongo import MongoClient

from flask import Flask
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
        files_per_result = 10

        @app.route("/")
        def show_index():
            return render_template("index.html", torrents_count=db.torrents.count())

        def render_results(query, page, elapsed_time, results):
            items = list(results)

            arguments = {
                "query": "",
                "page": page,
                "total_pages": len(items) / results_per_page,
                "time_elapsed": round(elapsed_time, 3),
                "results": map(lambda item: {
                    "info_hash": item["info_hash"],
                    "title": item["name"],
                    "size": __get_files_size(item["files"]),
                    "files": __get_files_list(item["files"], first_ten=True),
                    "lots_of_files": len(item["files"]) > files_per_result
                }, items)
            }

            return render_template("results.html", **arguments)

        @app.route("/search")
        def search():
            query = request.args.get("q")
            page = request.args.get("p", default=0)

            start_time = time()
            # Query database
            results = db.torrents.find(
                {"$text": {"$search": query}},
                {"score": {"$meta": "textScore"}}
            ).skip(page * results_per_page).limit(results_per_page)

            elapsed_time = time() - start_time

            return render_results(query, page, elapsed_time, results)

        @app.route("/latest")
        def latest():
            page = request.args.get("p", default=0)

            start_time = time()
            # Query database
            results = db.torrents.find().skip(page * results_per_page).limit(results_per_page)

            elapsed_time = time() - start_time

            return render_results("", page, elapsed_time, results)

        @app.route("/details")
        def details():
            query = request.args.get("q")
            info_hash = request.args.get("t")

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
                return "Not found", 404

        app.run(host=host, port=port)
    finally:
        mongo_client.close()
