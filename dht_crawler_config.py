# Database address
WEB_SERVER_API_URL = "http://127.0.0.1:8081/api"

DHT_CRAWLER_NODES_INFO = map(lambda port: {"port": port, "node_id": None},
                             xrange(6882, 6902, 2))
