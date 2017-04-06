"""
Package for interacting on the network at a high level.
"""
import binascii
import pickle

from twisted.internet.task import LoopingCall
from twisted.internet import defer, reactor, task

from log import Logger
from protocol import KademliaProtocol
from utils import deferred_dict
from ..common_utils import generate_node_id
from storage import ForgetfulStorage
from node import Node
from crawling import ValueSpiderCrawl
from crawling import NodeSpiderCrawl


class Server(object):
    """
    High level view of a node instance.  This is the object that should be created
    to start listening as an active node on the network.
    """

    def __init__(self, ksize=20, alpha=3, id=None, storage=None):
        """
        Create a server instance.  This will start listening on the given port.

        Args:
            ksize (int): The k parameter from the paper
            alpha (int): The alpha parameter from the paper
            id: The id for this node on the network.
            storage: An instance that implements :interface:`~kademlia.storage.IStorage`
        """
        self.ksize = ksize
        self.alpha = alpha
        self.log = Logger(system=self)
        self.storage = storage or ForgetfulStorage(ttl=30 * 60)
        self.node = Node(id or generate_node_id())
        self.protocol = KademliaProtocol(self.node, self.storage, ksize)
        self.refreshLoop = LoopingCall(self.refresh_table).start(3600)

    def listen(self, port, interface=""):
        """
        Start listening on the given port.

        This is the same as calling::

            reactor.listenUDP(port, server.protocol)

        Provide interface="::" to accept ipv6 address
        """
        return reactor.listenUDP(port, self.protocol, interface)

    def refresh_table(self):
        """
        Refresh buckets that haven't had any lookups in the last hour
        (per section 2.3 of the paper).
        """
        ds = []
        for id in self.protocol.getRefreshIDs():
            node = Node(id)
            nearest = self.protocol.router.findNeighbors(node, self.alpha)
            spider = NodeSpiderCrawl(self.protocol, node, nearest, self.ksize, self.alpha)
            ds.append(spider.find())

        def republishKeys(_):
            ds = []
            # Republish keys older than one hour
            for dkey, value in self.storage.iteritemsOlderThan(3600):
                ds.append(self.digest_set(dkey, value))
            return defer.gatherResults(ds)

        return defer.gatherResults(ds).addCallback(republishKeys)

    def bootstrappable_neighbors(self):
        """
        Get a :class:`list` of (ip, port) :class:`tuple` pairs suitable for use as an argument
        to the bootstrap method.

        The server should have been bootstrapped
        already - this is just a utility for getting some neighbors and then
        storing them if this server is going down for a while.  When it comes
        back up, the list of nodes can be used to bootstrap.
        """
        neighbors = self.protocol.router.findNeighbors(self.node)
        return [tuple(n)[-2:] for n in neighbors]

    def bootstrap(self, addrs):
        """
        Bootstrap the server by connecting to other known nodes in the network.

        Args:
            addrs: A `list` of (ip, port) `tuple` pairs.  Note that only IP addresses
                   are acceptable - hostnames will cause an error.
        """
        # if the transport hasn't been initialized yet, wait a second
        if self.protocol.transport is None:
            return task.deferLater(reactor, 1, self.bootstrap, addrs)

        def init_table(results):
            nodes = []
            for addr, result in results.items():
                if result[0]:
                    nodes.append(Node(result[1]["id"], addr[0], addr[1]))
            spider = NodeSpiderCrawl(self.protocol, self.node, nodes, self.ksize, self.alpha)
            return spider.find()

        ds = {}
        for addr in addrs:
            ds[addr] = self.protocol.ping(addr, self.node.id)
        return deferred_dict(ds).addCallback(init_table)

    def inet_visible_ip(self):
        """
        Get the internet visible IP's of this node as other nodes see it.

        Returns:
            A `list` of IP's.  If no one can be contacted, then the `list` will be empty.
        """

        def handle(results):
            ips = [result[1][0] for result in results if result[0]]
            self.log.debug("other nodes think our ip is %s" % str(ips))
            return ips

        ds = []
        for neighbor in self.bootstrappable_neighbors():
            ds.append(self.protocol.stun(neighbor))
        return defer.gatherResults(ds).addCallback(handle)

    def get_peers(self, info_hash):
        """
        Get a key if the network has it.

        Returns:
            :class:`None` if not found, the value otherwise.
        """
        # if this node has it, return it
        if self.storage.get(info_hash) is not None:
            return defer.succeed(self.storage.get(info_hash))
        node = Node(info_hash)
        nearest = self.protocol.router.findNeighbors(node)
        if len(nearest) == 0:
            self.log.warning("There are no known neighbors to get key %s" % info_hash)
            return defer.succeed(None)
        spider = ValueSpiderCrawl(self.protocol, node, nearest, self.ksize, self.alpha)
        return spider.find()

    def announce_peer(self, info_hash, port):
        """
        Set the given key to the given value in the network.
        """
        self.log.debug("setting '%s' = '%s' on network" % (info_hash, port))

        key = Node(info_hash)
        # this is useful for debugging messages
        hkey = binascii.hexlify(info_hash)

        def _any_announce_respond_success(responses):
            for defer_success, result in responses:
                peer_reached, peer_response, node = result
                if defer_success and peer_reached and peer_response:
                    return True

            return False

        def _any_get_peers_respond_success(responses):
            ds = []

            for defer_success, result in responses:
                peer_reached, peer_response, node = result
                if defer_success and peer_reached and "token" in peer_response:
                    ds.append(self.protocol.callAnnouncePeer(node, key, port, peer_response["token"]))

            if ds:
                return defer.DeferredList(ds).addCallback(_any_announce_respond_success)
            else:
                return False

        def _store(nodes):
            self.log.info("setting '%s' on %s" % (hkey, map(str, nodes)))
            # if this node is close too, then store here as well
            if self.node.distanceTo(key) < max([n.distanceTo(key) for n in nodes]):
                self.storage[info_hash] = port

            ds = [self.protocol.callGetPeers(n, key) for n in nodes]
            return defer.DeferredList(ds).addCallback(_any_get_peers_respond_success)

        nearest = self.protocol.router.findNeighbors(key)

        if len(nearest) == 0:
            self.log.warning("There are no known neighbors to set key %s" % hkey)
            return defer.succeed(False)

        spider = NodeSpiderCrawl(self.protocol, key, nearest, self.ksize, self.alpha)
        return spider.find().addCallback(_store)

    def save_state(self, fname):
        """
        Save the state of this node (the alpha/ksize/id/immediate neighbors)
        to a cache file with the given fname.
        """
        data = {'ksize': self.ksize,
                'alpha': self.alpha,
                'id': self.node.id,
                'neighbors': self.bootstrappable_neighbors()}
        if len(data['neighbors']) == 0:
            self.log.warning("No known neighbors, so not writing to cache.")
            return
        with open(fname, 'w') as f:
            pickle.dump(data, f)

    @staticmethod
    def load_state(fname):
        """
        Load the state of this node (the alpha/ksize/id/immediate neighbors)
        from a cache file with the given fname.
        """
        with open(fname, 'r') as f:
            data = pickle.load(f)
        s = Server(data['ksize'], data['alpha'], data['id'])
        if len(data['neighbors']) > 0:
            s.bootstrap(data['neighbors'])
        return s

    def save_state_regularly(self, fname, frequency=600):
        """
        Save the state of node with a given regularity to the given
        filename.

        Args:
            fname: File name to save retularly to
            frequency: Frequency in seconds that the state should be saved.
                        By default, 10 minutes.
        """
        loop = LoopingCall(self.save_state, fname)
        loop.start(frequency)
        return loop
