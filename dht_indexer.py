from threading import Thread
from multiprocessing import Process
from dht_indexer_config import *
from service.indexer import start_indexer


def watchdog_thread(**kwargs):
    while True:
        p = Process(target=start_indexer, kwargs=kwargs)
        p.start()  # Startup new process
        p.join()


def start_indexers(web_server_api_url, indexers_info):
    threads = []

    for indexer_info in indexers_info:
        kwargs = {
            "web_server_api_url": web_server_api_url,
            "port": indexer_info["port"],
            "node_id": indexer_info["node_id"],
            "bootstrap_node_address": indexer_info["bootstrap"],
            "time_to_live": 30 * 60  # Stop process after 30 minutes
        }

        t = Thread(target=watchdog_thread, kwargs=kwargs)
        t.start()
        threads.append(t)

    # Wait until all processes end
    map(lambda thread: thread.join(), threads)


if __name__ == '__main__':
    start_indexers(web_server_api_url=WEB_SERVER_API_URL,
                   indexers_info=DHT_INDEXERS_INFO)
