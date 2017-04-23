from config import *
from service.indexer import start_indexer

if __name__ == '__main__':
    start_indexer(mongodb_uri=MONGODB_URI,
                  port=DHT_INDEXER_PORT,
                  node_id=DHT_INDEXER_NODE_ID)