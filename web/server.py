from pymongo import MongoClient

from flask import Flask
from flask import render_template
from flask import request

from time import time

"""
MongoDB collection format:
{
   "files":[
      {
         "path":[
            "filename"
         ],
         "length":123
      },
      ...
   ],
   "name":"torrent name",
   "info_hash":"hex_info_hash_lower_case"
}
"""


def __sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)

        num /= 1024.0

    return "%.1f %s%s" % (num, "Y", suffix)


def __get_files_list(files):
    return map(lambda f: {"name": reduce(lambda r, e: r + e, f["path"], ""),
                          "size": __sizeof_fmt(f["length"])}, files)


def __get_files_size(files):
    return __sizeof_fmt(reduce(lambda r, e: r + e["length"], files, 0))


def start_server(mongodb_uri, host, port):
    mongo_client = MongoClient(mongodb_uri)
    try:
        grapefruit = mongo_client.torrents

        app = Flask(__name__, static_url_path="")

        @app.route("/")
        def show_index():
            return render_template("index.html")

        @app.route("/search")
        def search():
            query = request.args.get("q")
            page = request.args.get("p", default=1)

            start_time = time()
            # Query database
            results = grapefruit.torrents.find()
            elapsed_time = time() - start_time

            arguments = {
                "query": query,
                "page": page,
                "time_elapsed": elapsed_time,
                "results": map(lambda item: {
                    "info_hash": item["info_hash"],
                    "title": item["name"],
                    "size": __get_files_size(item["files"]),
                    "files": __get_files_list(item["files"])
                }, results)
            }

            return render_template("results.html", **arguments)

        @app.route("/details")
        def details():
            query = request.args.get("q")

            # Query database
            result = grapefruit.torrents.find_one({"info_hash": query})

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
