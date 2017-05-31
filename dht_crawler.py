from multiprocessing import Process

from dht_crawler_config import *
from service.crawler import start_crawler


def start_crawlers(web_server_api_url, nodes_info):
    """
    :param web_server_api_url: web server api url
    :param nodes_info: List of node info dicts ({"port": 123, "node_id": "456..."})
    :return: None
    """
    processes = []

    for node_info in nodes_info:
        args = {
            "web_server_api_url": web_server_api_url,
            "port": node_info["port"],
            "node_id": node_info["node_id"]
        }

        p = Process(target=start_crawler, kwargs=args)
        p.start()  # Startup new process

        processes.append(p)

    # Wait until all processes end
    map(lambda process: process.join(), processes)


if __name__ == '__main__':
    start_crawlers(web_server_api_url=WEB_SERVER_API_URL,
                   nodes_info=DHT_CRAWLER_NODES_INFO)
