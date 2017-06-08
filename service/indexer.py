import requests
import json
from torrent import load_torrent


def __get_hash_iterator(api_url):
    # This method return fetch method, who will reload torrent list, when he is empty
    def load_torrents():
        url = "{0}/fetch_torrents_for_load".format(api_url)

        api_response = requests.get(url, params={"limit": 10, "inc_access_count": True}).json()

        results = api_response["result"]
        if results and isinstance(results, list):
            return results
        else:
            return []

    # Local torrent items storage, using for closure from fetch_next_item
    torrents = []

    def fetch_next_item():
        if not torrents:
            torrents.extend(load_torrents())

        if torrents:
            return torrents.pop(0)
        else:
            return None

    return fetch_next_item


def __store_metadata(api_url, metadata):
    try:
        url = "{0}/add_torrent".format(api_url)
        data = {"info_hash": metadata["info_hash"],
                "metadata": json.dumps(
                    {"name": metadata["name"],
                     "files": map(lambda f: {"path": f["path"],
                                             "length": f["length"]},
                                  metadata["files"])})
                }
        requests.post(url, data=data)
    except:  # Ignore any exceptions.
        # TODO: Need to fix "error reading utf-8" error when invoke "json.dumps" function
        pass


def start_indexer(web_server_api_url, port, node_id=None, bootstrap_node_address=("router.bittorrent.com", 6881)):
    info_hash_iterator = __get_hash_iterator(web_server_api_url)

    load_torrent(bootstrap_node_address, port,
                 node_id=node_id,
                 workers_count=50,
                 on_get_info_hash=lambda: info_hash_iterator(),
                 on_got_metadata=lambda metadata: __store_metadata(web_server_api_url, metadata))
