import binascii
import sys

from twisted.internet import reactor
from twisted.python import log

from service.dht.network import Server

log.startLogging(sys.stdout)


def done(result):
    print "Found peers:", result
    reactor.stop()


def bootstrap_done(found, server, info_hash):
    if len(found) == 0:
        print "Could not connect to the bootstrap server."
        reactor.stop()
    else:
        print "Bootstrap completed"

        # server.announce_peer(info_hash, 12357).addCallback(done)
        server.get_peers(info_hash).addCallback(done)


def start_dht_server(ip):
    # debian-live-8.7.1-amd64-standard.iso.torrent
    info_hash = binascii.unhexlify("ac241759f92572e63de1ffdd1ea6baad8e5b236f")

    server = Server(id=binascii.unhexlify("cd2e6673b9f2a21cad1e605fe5fb745b9f7a214d"))
    server.listen(12346)
    server.bootstrap([(ip, 6881)]).addCallback(bootstrap_done, server, info_hash)


reactor.resolve("router.bittorrent.com").addCallback(start_dht_server)
reactor.run()
