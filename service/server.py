from pymongo import MongoClient
from binascii import hexlify, unhexlify
from twisted.internet import reactor

from bittorrent.bittorrent import BitTorrentFactory
from dht.server.network import Server
from dht.common_utils import generate_node_id

"""
MongoDB collection format:
{
   "files":[
      {
         "path":[
            "filename"
         ],
         "length":123
      },
      ...
   ],
   "name":"torrent name",
   "info_hash":"hex_info_hash_lower_case"
}
"""


def start_server(mongodb_uri, crawler_port, server_port, crawler_node_id=None, server_node_id=None):
    srv_node_id = server_node_id or generate_node_id()
    bt_peer_id = srv_node_id

    mongo_client = MongoClient(mongodb_uri)
    try:
        db = mongo_client.grapefruit

        def print_metadata(metadata, info_hash):
            torrent_hash = hexlify(info_hash)

            if db.torrents.find_one({"info_hash": torrent_hash}) is not None:
                assert "name" in metadata and "files" in metadata

                item = {
                    "info_hash": torrent_hash,
                    "name": metadata["name"],
                    "files": metadata["files"]
                }

                db.torrents.insert_one(item)

        def peers_found(peers, info_hash):
            for peer in peers:
                factory = BitTorrentFactory(info_hash=info_hash,
                                            peer_id=bt_peer_id,
                                            on_metadata_loaded=print_metadata)

                ip, port = peer
                reactor.connectTCP(ip, port, factory)

        def bootstrap_done(found, server, info_hash):
            if len(found) == 0:
                print "Could not connect to the bootstrap server."
                reactor.stop()
            else:
                server.get_peers(info_hash).addCallback(peers_found, info_hash)

        def start_dht_server(ip):
            # ubuntu-14.04.5-desktop-amd64.iso
            info_hash = unhexlify("34930674ef3bb9317fb5f263cca830f52685235b")

            server = Server(id=srv_node_id)
            server.listen(server_port)
            server.bootstrap([(ip, 6881)]).addCallback(bootstrap_done, server, info_hash)

        reactor.resolve("router.bittorrent.com").addCallback(start_dht_server)
        reactor.run()
    finally:
        mongo_client.close()
