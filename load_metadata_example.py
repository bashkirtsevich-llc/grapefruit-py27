import binascii
import sys

from twisted.internet import reactor
from twisted.python import log

from service.dht.network import Server

from service.bittorrent.bittorrent import BitTorrentFactory

log.startLogging(sys.stdout)


def print_metadata(metadata, info_hash):
    print "Torrent hash:", binascii.hexlify(info_hash)
    print "Torrent metadata:", metadata


def peers_found(peers, info_hash):
    print "Found peers:", peers

    for peer in peers:
        factory = BitTorrentFactory(info_hash=info_hash,
                                    peer_id=binascii.unhexlify("cd2e6673b9f2a21cad1e605fe5fb745b9f7a214d"),
                                    on_metadata_loaded=print_metadata)

        ip, port = peer
        print "Try request metadata from", ip, port
        reactor.connectTCP(ip, port, factory)


def bootstrap_done(found, server, info_hash):
    if len(found) == 0:
        print "Could not connect to the bootstrap server."
        reactor.stop()
    else:
        print "Bootstrap completed, request metadata"

        # server.announce_peer(info_hash, 12357).addCallback(done)
        server.get_peers(info_hash).addCallback(peers_found, info_hash)


def start_dht_server(ip):
    info_hash = binascii.unhexlify("04bc6703517e6f0ea13fd2561b36145af3ef35f1")

    server = Server(id=binascii.unhexlify("cd2e6673b9f2a21cad1e605fe5fb745b9f7a214d"))
    server.listen(12346)
    server.bootstrap([(ip, 6881)]).addCallback(bootstrap_done, server, info_hash)


reactor.resolve("router.bittorrent.com").addCallback(start_dht_server)
reactor.run()
