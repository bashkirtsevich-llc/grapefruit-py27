import requests
import json
from torrent import load_torrent


def __store_metadata(api_url, metadata, *args, **kwargs):
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
    finally:
        __index_next_info_hash(api_url, *args, **kwargs)


def __get_hash_iterator(api_url):
    # This method return fetch method, who will reload torrent list, when he is empty
    def load_torrents():
        url = "{0}/fetch_torrents_for_load".format(api_url)

        api_response = requests.get(url, params={"limit": 50, "inc_access_count": False}).json()

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


def __index_next_info_hash(api_url, try_load_metadata, get_next_info_hash):
    try_load_metadata(
        info_hash=get_next_info_hash(),
        schedule=60,  # Wait 60 seconds
        on_torrent_loaded=lambda metadata: __store_metadata(api_url, metadata, try_load_metadata, get_next_info_hash),
        on_torrent_not_found=lambda: __index_next_info_hash(api_url, try_load_metadata, get_next_info_hash)
    )


def __index_torrents(api_url, try_load_metadata):
    iterator = __get_hash_iterator(api_url)

    for _ in xrange(10):
        __index_next_info_hash(api_url, try_load_metadata, iterator)


def start_indexer(web_server_api_url, port, node_id=None, bootstrap_node_address=("router.bittorrent.com", 6881)):
    load_torrent(bootstrap_node_address, port,
                 node_id=node_id,
                 on_bootstrap_done=lambda try_load_metadata: __index_torrents(web_server_api_url, try_load_metadata))
