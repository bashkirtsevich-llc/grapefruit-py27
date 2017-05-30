from multiprocessing import Process
from dht_indexer_config import *
from service.indexer import start_indexer

def start_indexers(web_server_api_url, indexers_info):
    processes = []

    for indexer_info in indexers_info:
        args = {
            "web_server_api_url": web_server_api_url,
            "port": indexer_info["port"],
            "node_id": indexer_info["node_id"],
            "bootstrap_node_address": indexer_info["bootstrap"]
        }

        p = Process(target=start_indexer, kwargs=args)
        p.start()  # Startup new process

        processes.append(p)

    # Wait until all processes end
    map(lambda process: process.join(), processes)

if __name__ == '__main__':
    start_indexers(web_server_api_url=WEB_SERVER_API_URL,
                   indexers_info=DHT_INDEXERS_INFO)
