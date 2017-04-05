import random

from base64 import b64encode

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from rpcudp.protocol import RPCProtocol

from node import Node
from routing import RoutingTable
from log import Logger

from struct import pack

from bencode import bencode, bdecode, BTFailure

from utils import encode_nodes, generate_token, verify_token, encode_values


class KademliaProtocol(RPCProtocol):
    def __init__(self, sourceNode, storage, ksize):
        RPCProtocol.__init__(self)
        self.router = RoutingTable(self, ksize, sourceNode)
        self.storage = storage
        self.sourceNode = sourceNode
        self.log = Logger(system=self)
        self.transactionSeq = 0

    def datagramReceived(self, datagram, address):
        if self.noisy:
            log.msg("received datagram from %s" % repr(address))

        try:
            msg = bdecode(datagram)
            msgID = msg["t"]
            msgType = msg["y"]

            if msgType == "q":
                f = getattr(self, "rpc_%s" % msg["q"], None)

                if f is None or not callable(f):
                    self.transport.write(bencode({
                        "t": msgID,
                        "y": "e",
                        "e": [204, "Method Unknown"]}),
                        address
                    )
                else:
                    self._acceptRequest(msgID, [msg["q"], [msg["a"]]], address)

            elif msgType == "r":
                self._acceptResponse(msgID, msg["r"], address)

            elif msgType == "e":
                # Ignore error messages
                pass
            else:
                # otherwise, don't know the format, don't do anything
                log.msg("Received unknown message from %s, ignoring" % repr(address))

                self.transport.write(bencode({
                    "t": msgID,
                    "y": "e",
                    "e": [203, "Protocol Error, invalid arguments"]}),
                    address
                )

        except KeyError:
            log.msg("Invalid message data from %s, ignoring" % repr(address))

            self.transport.write(bencode({
                "y": "e",
                "e": [201, "Generic Error"]}),
                address
            )

        except BTFailure:
            log.msg("Not a valid bencoded string from %s, ignoring" % repr(address))

            self.transport.write(bencode({
                "y": "e",
                "e": [203, "Protocol Error, malformed packet"]}),
                address
            )

    def _sendResponse(self, response, msgID, address):
        if self.noisy:
            log.msg("sending response for msg id %s to %s" % (b64encode(msgID), repr(address)))

        response["t"] = msgID

        self.transport.write(bencode(response), address)

    def sendMessage(self, address, message):
        msgID = pack(">I", self.transactionSeq)
        self.transactionSeq += 1

        message["t"] = msgID

        self.transport.write(bencode(message), address)

        d = defer.Deferred()
        timeout = reactor.callLater(self._waitTimeout, self._timeout, msgID)

        self._outstanding[msgID] = (d, timeout)
        return d

    def getRefreshIDs(self):
        """
        Get ids to search for to keep old buckets up to date.
        """
        ids = []
        for bucket in self.router.getLonelyBuckets():
            ids.append(random.randint(*bucket.range))
        return ids

    @staticmethod
    def _response_error(error_code, error_message):
        return {"y": "e",
                "e": [error_code, error_message]}

    def rpc_ping(self, sender, args):
        try:
            node_id = args["id"]
            source = Node(node_id, sender[0], sender[1])

            self.welcomeIfNewNode(source)

            return {"y": "r",
                    "r": {"id": self.sourceNode.id}}
        except KeyError:
            return self._response_error(203, "Protocol Error, invalid arguments")

    def rpc_announce_peer(self, sender, args):
        try:
            node_id = args["id"]
            info_hash = args["info_hash"]
            port = args["port"]
            token = args["token"]

            source = Node(node_id, sender[0], sender[1])

            self.welcomeIfNewNode(source)

            self.log.debug("got a store request from %s, storing value" % str(sender))

            if verify_token(sender[0], sender[1], token):
                values = self.storage.get(info_hash, [])
                values.append((sender[0], port))

                # Redeclare value by info_hash
                self.storage[info_hash] = values

                return {"y": "r",
                        "r": {"id": self.sourceNode.id}}
            else:
                return self._response_error(203, "Protocol Error, bad token")
        except KeyError:
            return self._response_error(203, "Protocol Error, invalid arguments")

    def rpc_find_node(self, sender, args):
        try:
            node_id = args["id"]
            target = args["target"]

            self.log.info("finding neighbors of %i in local table" % long(node_id.encode('hex'), 16))

            source = Node(node_id, sender[0], sender[1])
            self.welcomeIfNewNode(source)

            node = Node(target)

            return {"y": "r",
                    "r": {"id": self.sourceNode.id,
                          "nodes": encode_nodes(self.router.findNeighbors(node, exclude=source))}}
        except KeyError:
            return self._response_error(203, "Protocol Error, invalid arguments")

    def rpc_get_peers(self, sender, args):
        try:
            node_id = args["id"]
            info_hash = args["info_hash"]

            source = Node(node_id, sender[0], sender[1])

            self.welcomeIfNewNode(source)

            values = self.storage.get(info_hash, None)
            if values is not None:
                # We must calculate unique token for sender
                return {"y": "r",
                        "r": {"id": self.sourceNode.id,
                              "token": generate_token(sender[0], sender[1]),
                              "values": encode_values(values)}}
            else:
                return self.rpc_find_node(sender, {"id": node_id,
                                                   "target": info_hash})
        except KeyError:
            return self._response_error(203, "Protocol Error, invalid arguments")

    def callFindNode(self, nodeToAsk, nodeToFind):
        address = (nodeToAsk.ip, nodeToAsk.port)
        d = self.find_node(address, self.sourceNode.id, nodeToFind.id)
        return d.addCallback(self.handleCallResponse, nodeToAsk, responseMessage="find_node")

    def callGetPeers(self, nodeToAsk, key):
        address = (nodeToAsk.ip, nodeToAsk.port)
        d = self.get_peers(address, self.sourceNode.id, key.id)
        return d.addCallback(self.handleCallResponse, nodeToAsk, responseMessage="get_peers")

    def callPing(self, nodeToAsk):
        address = (nodeToAsk.ip, nodeToAsk.port)
        d = self.ping(address, self.sourceNode.id)
        return d.addCallback(self.handleCallResponse, nodeToAsk, responseMessage="ping")

    def callAnnouncePeer(self, nodeToAsk, key, value, token):
        address = (nodeToAsk.ip, nodeToAsk.port)
        d = self.announce_peer(address, self.sourceNode.id, key.id, value, token)
        return d.addCallback(self.handleCallResponse, nodeToAsk, responseMessage="announce_peer")

    # BitTorrent protocol messages implementation
    def ping(self, address, nodeId):
        return self.sendMessage(address, {"y": "q",
                                          "q": "ping",
                                          "a": {"id": nodeId}})

    def find_node(self, address, nodeId, targetId):
        return self.sendMessage(address, {"y": "q",
                                          "q": "find_node",
                                          "a": {"id": nodeId,
                                                "target": targetId}})

    def get_peers(self, address, nodeId, info_hash):
        return self.sendMessage(address, {"y": "q",
                                          "q": "get_peers",
                                          "a": {"id": nodeId,
                                                "info_hash": info_hash}})

    def announce_peer(self, address, nodeId, info_hash, port, token):
        return self.sendMessage(address, {"y": "q",
                                          "q": "announce_peer",
                                          "a": {"id": nodeId,
                                                "implied_port": 0,
                                                "info_hash": info_hash,
                                                "port": port,
                                                "token": token}})

    def welcomeIfNewNode(self, node):
        if self.router.isNewNode(node):
            self.router.addContact(node)

    def handleCallResponse(self, result, node, responseMessage):
        """
        If we get a response, add the node to the routing table.  If
        we get no response, make sure it's removed from the routing table.
        """
        if result[0]:
            self.log.info("got response from %s, adding to router" % node)
            self.welcomeIfNewNode(node)
        else:
            self.log.debug("no response from %s, removing from router" % node)
            self.router.removeContact(node)

        # TODO: Its looks like a software crutch, need some solution to avoid it.
        return result + (node,)
