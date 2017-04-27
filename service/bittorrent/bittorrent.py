from twisted.internet import reactor
from protocol import BitTorrentFactory


class ConnectionLink:
    def __init__(self, peers, info_hash, peer_id, on_metadata_loaded, on_metadata_not_found):
        self._on_metadata_loaded = on_metadata_loaded
        self._on_metadata_not_found = on_metadata_not_found

        # Need critical sections? Is "reactor" single thread?
        self._connections = {}
        self._got_metadata = False

        for peer in peers:
            self._register_connection(peer, info_hash, peer_id)

    def _register_connection(self, peer, info_hash, peer_id):
        factory = BitTorrentFactory(
            info_hash=info_hash,
            peer_id=peer_id,
            on_metadata_loaded=lambda metadata, torrent_hash: self._on_got_metadata(peer, metadata, torrent_hash),
            on_error=lambda error: self._forget_connection(peer)
        )

        self._connections[peer] = factory

    def _forget_connection(self, peer):
        if peer in self._connections:
            del self._connections[peer]

            if not self._connections and not self._got_metadata and callable(self._on_metadata_not_found):
                self._on_metadata_not_found()

    def _on_got_metadata(self, peer, metadata, torrent_hash):
        # Used for callback "_on_metadata_loaded" once.
        can_callback = False

        if not self._got_metadata:
            self._got_metadata = True
            can_callback = True

        self._forget_connection(peer)

        if can_callback and callable(self._on_metadata_loaded):
            self._on_metadata_loaded(metadata, torrent_hash)

    def connect(self):
        for peer in self._connections.keys():
            peer_ip, peer_port = peer
            reactor.connectTCP(peer_ip, peer_port, self._connections[peer], timeout=10)


class ConnectionChain:
    def __init__(self, peers, info_hash, peer_id, on_metadata_loaded, on_metadata_not_found, link_size=10):
        self._on_metadata_loaded = on_metadata_loaded
        self._on_metadata_not_found = on_metadata_not_found

        self._links = []
        self._got_metadata = False

        for i in xrange(0, len(peers), link_size):
            self._links.append(
                ConnectionLink(
                    peers=peers[i:i + link_size],
                    info_hash=info_hash,
                    peer_id=peer_id,
                    on_metadata_loaded=self._on_got_metadata,
                    on_metadata_not_found=self._connect_next_link
                )
            )

    def connect(self):
        self._connect_next_link()

    def _on_got_metadata(self, metadata, torrent_hash):
        self._got_metadata = True

        if callable(self._on_metadata_loaded):
            self._on_metadata_loaded(metadata, torrent_hash)

    def _connect_next_link(self):
        if not self._got_metadata:
            if self._links:
                link = self._links.pop(0)
                link.connect()
            elif callable(self._on_metadata_not_found):
                self._on_metadata_not_found()
