from flask import Flask
from flask import render_template
from flask import request


def start_server(host, port):
    app = Flask(__name__, static_url_path='')

    @app.route("/")
    def show_index():
        return render_template("index.html")

    @app.route("/search")
    def search():
        query = request.args.get('q')
        page = request.args.get('p', default=1)
        arguments = {
            "query": query,
            "page": page,
            "time_elapsed": 0.05,
            "results": [{
                "info_hash": "52BD13E80E8EC1661BF8DDDC3C428358F12B7CEA",
                "title": "test1",
                "size": "100 MB",
                "files": [{
                    "name": "test.iso",
                    "size": "100 MB"
                }]
            }, {
                "info_hash": "52BD13E80E8EC1661BF8DDDC3C428358F12B7CEA",
                "title": "test2",
                "size": "200 MB",
                "files": [{
                    "name": "test1.jpg",
                    "size": "1 MB"
                }, {
                    "name": "test2.jpg",
                    "size": "199 MB"
                }, ]
            }]
        }
        return render_template("results.html", **arguments)

    @app.route("/details")
    def details():
        query = request.args.get('q')
        arguments = {
            "query": query,
            "title": "test",
            "size": "100 MB",
            "info_hash": "52BD13E80E8EC1661BF8DDDC3C428358F12B7CEA",
            "files": [{
                "name": "test.jpg",
                "size": "1 MB"
            }, {
                "name": "test2.jpg",
                "size": "199 MB"
            }, ]
        }
        return render_template("details.html", **arguments)

    app.run(host=host, port=port)
