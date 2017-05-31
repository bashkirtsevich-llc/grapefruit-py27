# Database address
WEB_SERVER_API_URL = "http://127.0.0.1:8081/api"

DHT_DEFAULT_BOOTSTRAP_ADDRESS = ("router.bittorrent.com", 6881)

DHT_INDEXERS_INFO = map(lambda port: {"port": port,
                                      "node_id": None,
                                      "bootstrap": DHT_DEFAULT_BOOTSTRAP_ADDRESS},
                        xrange(6881, 6901, 2))
