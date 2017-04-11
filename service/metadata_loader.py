from binascii import hexlify
from twisted.internet import reactor

from bittorrent.bittorrent import BitTorrentFactory
from dht.server.network import Server
from dht.common_utils import generate_node_id, generate_peer_id


def metadata_loader(bootstrap_host, bootstrap_port, port, **kwargs):
    """
    :param bootstrap_host: DHT-bootstrap host name
    :param bootstrap_port: DHT-bootstrap connection port
    :param port: Local DHT-server port
    :param kwargs: node_id, peer_id, on_bootstrap_done, on_bootstrap_failed
    :return: None
    """

    def metadata_loaded(metadata, info_hash, on_metadata_loaded):
        if on_metadata_loaded is not None:
            assert callable(on_metadata_loaded)

            args = {
                "info_hash": hexlify(info_hash),
                "name": metadata["name"],
                "files": metadata["files"] if "files" in metadata else [
                    {"path": [metadata["name"]], "length": metadata["length"]}]
            }

            reactor.callInThread(on_metadata_loaded, args)

    def peers_found(peers, info_hash, on_metadata_loaded):
        for peer in peers:
            factory = BitTorrentFactory(info_hash=info_hash,
                                        peer_id=kwargs.get("peer_id", generate_peer_id()),
                                        on_metadata_loaded=lambda metadata, info_hash: metadata_loaded(
                                            metadata, info_hash, on_metadata_loaded))

            ip, port = peer
            reactor.connectTCP(ip, port, factory)

    def get_peers(server, info_hash, on_metadata_loaded):
        server.get_peers(info_hash).addCallback(peers_found, info_hash, on_metadata_loaded)

    def bootstrap_done(found, server):
        if len(found) == 0:
            on_bootstrap_failed = kwargs.get("on_bootstrap_failed", None)
            if on_bootstrap_failed is not None:
                assert callable(on_bootstrap_failed)

                on_bootstrap_failed("Could not connect to the bootstrap server.")

            reactor.stop()
        else:
            on_bootstrap_done = kwargs.get("on_bootstrap_done", None)

            if on_bootstrap_done is not None:
                assert callable(on_bootstrap_done)

                reactor.callInThread(on_bootstrap_done,
                                     lambda info_hash, on_metadata_loaded: get_peers(server, info_hash,
                                                                                     on_metadata_loaded))

    def start_dht_server(ip):
        server = Server(id=kwargs.get("node_id", generate_node_id()))
        server.listen(port)
        server.bootstrap([(ip, bootstrap_port)]).addCallback(bootstrap_done, server)

    reactor.resolve(bootstrap_host).addCallback(start_dht_server)
    reactor.run()
