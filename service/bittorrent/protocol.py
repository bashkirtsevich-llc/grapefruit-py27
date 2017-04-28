# Source code from https://github.com/bashkirtsevich/Py-ut_metadata

from struct import pack, unpack
from binascii import unhexlify
from bencode import bencode, bdecode, decode_dict
from time import sleep
from hashlib import sha1
from twisted.internet import protocol, defer
from twisted.protocols import policies


class BitTorrentClient(protocol.Protocol, policies.TimeoutMixin):
    def __init__(self, info_hash, peer_id, on_metadata_loaded, on_error):
        self._info_hash = info_hash
        self._peer_id = peer_id

        self._buffer = buffer("")
        self._read_handshake = True
        self._metadata = {}

        self._deferred = defer.Deferred()
        self._deferred.addCallback(on_metadata_loaded, info_hash)
        self._deferred.addErrback(on_error)

    @staticmethod
    def parseMessage(message):
        # Return message code and message data
        if message:
            return (unpack("B", message[:1])[0], message[1:])
        else:
            return None

    def sendExtendedMessage(self, message_id, message_data):
        buf = pack("BB", 20, message_id) + bencode(message_data)

        self.transport.write(pack("!I", len(buf)) + buf)

    def handleMessage(self, msg_code, msg_data):
        if msg_code == 20:
            # If he send extended message, we can  time
            self.resetTimeout()

            # Extended handshake
            if ord(msg_data[0]) == 0:
                hs_data = bdecode(msg_data[1:])

                if "metadata_size" in hs_data and "m" in hs_data and "ut_metadata" in hs_data["m"]:
                    metadata_size = hs_data["metadata_size"]
                    ut_metadata_id = hs_data["m"]["ut_metadata"]

                    hs_response = {"e": 0,
                                   "metadata_size": hs_data["metadata_size"],
                                   "v": "\xce\xbcTorrent 3.4.9",
                                   "m": {"ut_metadata": 1},
                                   "reqq": 255}

                    # Response extended handshake
                    self.sendExtendedMessage(0, hs_response)

                    sleep(0.5)

                    # Request metadata
                    for i in range(0, 1 + metadata_size / (16 * 1024)):
                        self.sendExtendedMessage(ut_metadata_id, {"msg_type": 0, "piece": i})
                        sleep(0.05)
                else:
                    self._deferred.errback((11, "Peer has no necessary protocol extensions"))
                    self.transport.abortConnection()

            elif ord(msg_data[0]) == 1:
                r, l = decode_dict(msg_data[1:], 0)

                if r["msg_type"] == 1:
                    self._metadata[r["piece"]] = msg_data[l + 1:]

                    metadata = reduce(lambda r, e: r + self._metadata[e], sorted(self._metadata.keys()), "")

                    if len(metadata) == r["total_size"]:
                        if sha1(metadata).digest() == self._info_hash:
                            self._deferred.callback(bdecode(metadata))
                        else:
                            self._deferred.errback((12, "Wrong metadata hash"))

                        # Abort connection anyway
                        self.transport.abortConnection()

    def connectionMade(self):
        # Set connection timeout in 10 seconds (after 10 seconds idle connection will be aborted)
        self.setTimeout(10)
        # Send handshake
        bp = list("BitTorrent protocol")
        self.transport.write(pack("B19c", 19, *bp))
        self.transport.write(unhexlify("0000000000100005"))
        self.transport.write(self._info_hash)
        self.transport.write(self._peer_id)

    def dataReceived(self, data):
        self._buffer = buffer(self._buffer) + buffer(data)

        if self._read_handshake:
            if len(self._buffer) >= 68:
                # Skip handshake response
                self._buffer = self._buffer[68:]
                self._read_handshake = False
            else:
                return
        else:
            # Read regular message
            while self._buffer:
                msg_len = unpack("!I", self._buffer[:4])[0]

                if len(self._buffer) >= msg_len + 4:
                    message = self.parseMessage(self._buffer[4: msg_len + 4])
                    if message:
                        self.handleMessage(*message)

                    self._buffer = self._buffer[msg_len + 4:]
                else:
                    break

    def timeoutConnection(self):
        if not self._deferred.called:
            self._deferred.errback((10, "Connection aborted by timeout"))

        self.transport.abortConnection()


class BitTorrentFactory(protocol.ClientFactory):
    protocol = BitTorrentClient

    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._on_error = self._kwargs.get("on_error", None)

    def callback_error(self, code, reason):
        if callable(self._on_error):
            self._on_error((code, reason))

    def clientConnectionFailed(self, connector, reason):
        self.callback_error(1, reason)

    def clientConnectionLost(self, connector, reason):
        self.callback_error(2, reason)

    def buildProtocol(self, addr):
        p = self.protocol(**self._kwargs)
        p.factory = self
        return p
