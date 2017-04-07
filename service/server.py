from binascii import unhexlify
from pymongo import MongoClient

from metadata_loader import metadata_loader


def start_server(mongodb_uri, crawler_port, server_port, crawler_node_id=None, server_node_id=None):
    mongo_client = MongoClient(mongodb_uri)
    try:
        db = mongo_client.grapefruit

        def print_metadata(metadata):
            if db.torrents.find_one({"info_hash": metadata["info_hash"]}) is not None:
                db.torrents.insert_one(metadata)

        def bootstrap_done(searcher):
            # ubuntu-14.04.5-desktop-amd64.iso
            searcher(unhexlify("34930674ef3bb9317fb5f263cca830f52685235b"), print_metadata)

        metadata_loader("router.bittorrent.com", 6881, server_port, on_bootstrap_done=bootstrap_done)

    finally:
        mongo_client.close()
