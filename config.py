MONGODB_URI = "mongodb://localhost:27017/"  # Database address

WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = 8081
WEB_SERVER_API_ACCESS_HOST = "127.0.0.1"  # IP address, who can use server API

DHT_INDEXER_PORT = 6881
DHT_INDEXER_NODE_ID = None  # unhexlify("af1d003a5d93e94bfbbd57a6e6e05f5d7f8f92c6")

DHT_CRAWLER_NODES_INFO = map(lambda port: {"port": port, "node_id": None}, xrange(6882, 6892))

DHT_INDEXER_BOOTSTRAP_ADDRESS = ("router.bittorrent.com", 6881)
