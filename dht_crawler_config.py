# Database address
MONGODB_URI = "mongodb://localhost:27017/"

DHT_CRAWLER_NODES_INFO = map(lambda port: {"port": port, "node_id": None}, xrange(6882, 6892))
