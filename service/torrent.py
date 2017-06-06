from binascii import hexlify, unhexlify
from twisted.internet import reactor
from bittorrent.bittorrent import ConnectionChain
from dht.server.network import Server
from dht.common_utils import generate_node_id, generate_peer_id
from threading import Lock


def __torrent_loaded(metadata, info_hash, on_torrent_loaded):
    if callable(on_torrent_loaded):
        args = {
            "info_hash": hexlify(info_hash),
            "name": metadata["name"],
            "files": metadata["files"] if "files" in metadata else [
                {"path": [metadata["name"]], "length": metadata["length"]}]
        }

        on_torrent_loaded(args)


def __handle_peers(peers, info_hash, server, server_lock, global_lock,
                   on_get_info_hash, on_got_metadata):
    if peers:
        chain = ConnectionChain(peers, info_hash,
                                peer_id=generate_peer_id(),
                                on_metadata_loaded=lambda metadata, torrent_hash:
                                __torrent_loaded(metadata, torrent_hash, on_got_metadata),
                                link_size=20)
        chain.connect()

    with global_lock:
        reactor.callLater(1, __get_peers_next, server, server_lock, global_lock,
                          on_get_info_hash, on_got_metadata)


def __get_peers_next(server, server_lock, global_lock,
                     on_get_info_hash, on_got_metadata):
    info_hash = unhexlify(on_get_info_hash() or "")

    if info_hash:
        with server_lock:
            server.get_peers(info_hash).addCallback(
                __handle_peers, info_hash, server, server_lock, global_lock,
                on_get_info_hash, on_got_metadata)
    else:
        with global_lock:
            reactor.callLater(1, __get_peers_next, server, server_lock, global_lock,
                              on_get_info_hash, on_got_metadata)


def __bootstrap_done(found, server, server_lock, global_lock, **kwargs):
    if found:
        on_bootstrap_done = kwargs.get("on_bootstrap_done", None)

        if callable(on_bootstrap_done):
            on_bootstrap_done()

        workers_count = kwargs.get("workers_count", 0)
        on_get_info_hash = kwargs.get("on_get_info_hash", None)
        on_got_metadata = kwargs.get("on_got_metadata", None)

        if workers_count > 0 and callable(on_get_info_hash) and callable(on_got_metadata):
            for _ in xrange(workers_count):
                with global_lock:
                    reactor.callLater(1, __get_peers_next,
                                      server, server_lock, global_lock,
                                      on_get_info_hash, on_got_metadata)
    else:
        on_bootstrap_failed = kwargs.get("on_bootstrap_failed", None)

        if callable(on_bootstrap_failed):
            on_bootstrap_failed()

        reactor.stop()


def __start_dht_server(port, bootstrap_address, **kwargs):
    global_lock = Lock()
    server_lock = Lock()

    server = Server(id=kwargs.get("node_id", generate_node_id()))
    server.listen(port)
    server.bootstrap([bootstrap_address]).addCallback(
        __bootstrap_done, server, server_lock, global_lock, **kwargs)


def load_torrent(bootstrap_address, port, **kwargs):
    """
    :param bootstrap_host: DHT-bootstrap host name
    :param bootstrap_port: DHT-bootstrap connection port
    :param port: Local DHT-server port
    :param kwargs: node_id, peer_id, on_bootstrap_done, on_bootstrap_failed
    :return: None
    """

    reactor.resolve(bootstrap_address[0]).addCallback(
        lambda bootstrap_ip: __start_dht_server(port, (bootstrap_ip, bootstrap_address[1]), **kwargs))
    reactor.run()
