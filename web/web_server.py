from __future__ import division

import logging
import os

import urllib
import math

from flask import Flask
from flask import redirect
from flask import abort
from flask import render_template
from flask import request

from markupsafe import Markup

from pymongo import MongoClient

from utils import *
from api import *


def start_web_server(mongodb_uri, host, port):
    logging.basicConfig(filename=os.devnull,
                        level=logging.DEBUG)

    mongo_client = MongoClient(mongodb_uri)
    try:
        db_for_ui = mongo_client.grapefruit

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

        # Regular http requests
        @app.route("/")
        def show_index():
            return render_template("index.html",
                                   torrents_count=db_get_torrents_count(db_for_ui))

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
                    db_for_ui,
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
                db_for_ui,
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
                result, _ = db_get_torrent_details(db_for_ui, info_hash)

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