import os

from web.web_server import start_web_server
from web.api_server import start_api_server
from web_server_config import *

from multiprocessing import Process

if __name__ == '__main__':
    web = Process(
        target=start_web_server,
        kwargs=dict(
            mongodb_uri=MONGODB_URI,
            host=WEB_SERVER_HOST,
            port=WEB_SERVER_PORT)
    )

    api = Process(
        target=start_api_server,
        kwargs=dict(
            mongodb_uri=MONGODB_URI,
            host=API_SERVER_HOST,
            port=API_SERVER_PORT)
    )

    web.start()
    api.start()

    web.join()
    api.join()
