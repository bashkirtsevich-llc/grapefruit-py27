from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
from protocol import BitTorrentProtocol


class ConnectionLink:
    def __init__(self, peers, info_hash, peer_id, on_metadata_loaded, on_metadata_not_found):
        self._info_hash = info_hash
        self._peer_id = peer_id
        self._on_metadata_loaded = on_metadata_loaded
        self._on_metadata_not_found = on_metadata_not_found

        self._got_metadata = False

        self._connections = {}

        for peer in peers:
            self._connections[peer] = None

    def _forget_connection(self, peer):
        if self._connections.pop(peer, None):
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

            point = TCP4ClientEndpoint(reactor, peer_ip, peer_port, 10)

            conn = connectProtocol(
                point, BitTorrentProtocol(
                    info_hash=self._info_hash,
                    peer_id=self._peer_id,
                    on_metadata_loaded=self._on_metadata_loaded,
                    on_error=lambda error: self._forget_connection(peer)
                )
            )
            conn.addCallback(lambda protocol: protocol.sendHandshake())

            self._connections[peer] = conn


class ConnectionChain:
    def __init__(self, peers, info_hash, peer_id, on_metadata_loaded, on_metadata_not_found=None, link_size=10):
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
