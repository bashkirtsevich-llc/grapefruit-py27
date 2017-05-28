from multiprocessing import Process

from dht_crawler_config import MONGODB_URI, DHT_CRAWLER_NODES_INFO
from service.crawler import start_crawler


def start_crawlers(mongodb_uri, nodes_info):
    """
    :param mongodb_uri: Mongodb connection uri
    :param nodes_info: List of node info dicts ({"port": 123, "node_id": "456..."})
    :return: None
    """
    processes = []

    for node_info in nodes_info:
        args = {
            "mongodb_uri": mongodb_uri,
            "port": node_info["port"],
            "node_id": node_info["node_id"]
        }

        p = Process(target=start_crawler, kwargs=args)
        p.start()  # Startup new process

        processes.append(p)

    # Wait until all processes end
    map(lambda process: process.join(), processes)


if __name__ == '__main__':
    start_crawlers(mongodb_uri=MONGODB_URI,
                   nodes_info=DHT_CRAWLER_NODES_INFO)
