from binascii import hexlify
from twisted.internet import reactor

from bittorrent.bittorrent import BitTorrentFactory
from dht.server.network import Server
from dht.common_utils import generate_node_id, generate_peer_id


def load_torrent(bootstrap_address, port, **kwargs):
    """
    :param bootstrap_host: DHT-bootstrap host name
    :param bootstrap_port: DHT-bootstrap connection port
    :param port: Local DHT-server port
    :param kwargs: node_id, peer_id, on_bootstrap_done, on_bootstrap_failed
    :return: None
    """

    def torrent_loaded(metadata, info_hash, on_torrent_loaded):
        if on_torrent_loaded and callable(on_torrent_loaded):
            args = {
                "info_hash": hexlify(info_hash),
                "name": metadata["name"],
                "files": metadata["files"] if "files" in metadata else [
                    {"path": [metadata["name"]], "length": metadata["length"]}]
            }

            on_torrent_loaded(args)

    def handle_peers(peers, info_hash, on_torrent_loaded, on_no_peers_found):
        if peers:
            # We need to use chain loading. If first peer has no response -- try load from second, etc.
            for peer in peers:
                factory = BitTorrentFactory(info_hash=info_hash,
                                            peer_id=kwargs.get("peer_id", generate_peer_id()),
                                            on_metadata_loaded=lambda metadata, info_hash: torrent_loaded(
                                                metadata, info_hash, on_torrent_loaded))

                ip, port = peer
                reactor.connectTCP(ip, port, factory, timeout=10)

        elif on_no_peers_found and callable(on_no_peers_found):
            on_no_peers_found()

    def get_peers(server, info_hash, on_torrent_loaded, on_no_peers_found):
        server.get_peers(info_hash).addCallback(handle_peers, info_hash, on_torrent_loaded, on_no_peers_found)

    def bootstrap_done(found, server):
        if found:
            on_bootstrap_done = kwargs.get("on_bootstrap_done", None)

            if on_bootstrap_done and callable(on_bootstrap_done):
                on_bootstrap_done(lambda info_hash, on_torrent_loaded, on_no_peers_found:
                                  get_peers(server, info_hash, on_torrent_loaded, on_no_peers_found))
        else:
            on_bootstrap_failed = kwargs.get("on_bootstrap_failed", None)

            if on_bootstrap_failed and callable(on_bootstrap_failed):
                on_bootstrap_failed()

            reactor.stop()

    def start_dht_server(ip):
        server = Server(id=kwargs.get("node_id", generate_node_id()))
        server.listen(port)
        server.bootstrap([(ip, bootstrap_address[1])]).addCallback(bootstrap_done, server)

    reactor.resolve(bootstrap_address[0]).addCallback(start_dht_server)
    reactor.run()
