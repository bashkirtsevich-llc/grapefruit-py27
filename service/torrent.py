from binascii import hexlify, unhexlify
from twisted.internet import reactor
from bittorrent.bittorrent import ConnectionChain
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
        if callable(on_torrent_loaded):
            args = {
                "info_hash": hexlify(info_hash),
                "name": metadata["name"],
                "files": metadata["files"] if "files" in metadata else [
                    {"path": [metadata["name"]], "length": metadata["length"]}]
            }

            on_torrent_loaded(args)

    def connect_peers(peers, info_hash, on_torrent_loaded, on_torrent_not_found):
        if peers:
            # Will garbage collector drop it?
            chain = ConnectionChain(peers, info_hash,
                                    peer_id=kwargs.get("peer_id", generate_peer_id()),
                                    on_metadata_loaded=lambda metadata, torrent_hash:
                                    torrent_loaded(metadata, torrent_hash, on_torrent_loaded),
                                    on_metadata_not_found=on_torrent_not_found,
                                    link_size=20)
            chain.connect()

        elif callable(on_torrent_not_found):
            on_torrent_not_found()

    def get_peers(server, info_hash, on_torrent_loaded, on_torrent_not_found):
        # Guard info_hash
        if info_hash and len(info_hash) == 20:
            server.get_peers(info_hash).addCallback(connect_peers, info_hash,
                                                    on_torrent_loaded, on_torrent_not_found)

        elif callable(on_torrent_not_found):
            on_torrent_not_found()

    def bootstrap_done(found, server):
        if found:
            on_bootstrap_done = kwargs.get("on_bootstrap_done", None)

            if callable(on_bootstrap_done):
                on_bootstrap_done(lambda info_hash, on_torrent_loaded, on_torrent_not_found=None, schedule=0:
                                  # Invoke "get_peers" after "schedule" seconds
                                  reactor.callLater(schedule, get_peers,
                                                    server,
                                                    unhexlify(info_hash) if info_hash else None,
                                                    on_torrent_loaded, on_torrent_not_found))
        else:
            on_bootstrap_failed = kwargs.get("on_bootstrap_failed", None)

            if callable(on_bootstrap_failed):
                on_bootstrap_failed()

            reactor.stop()

    def start_dht_server(bootstrap_ip, bootstrap_port):
        server = Server(id=kwargs.get("node_id", generate_node_id()))
        server.listen(port)
        server.bootstrap([(bootstrap_ip, bootstrap_port)]).addCallback(bootstrap_done, server)

    reactor.resolve(bootstrap_address[0]).addCallback(start_dht_server, bootstrap_address[1])
    reactor.run()
