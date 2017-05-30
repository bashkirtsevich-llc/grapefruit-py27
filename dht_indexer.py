from dht_indexer_config import *
from service.indexer import start_indexer

if __name__ == '__main__':
    start_indexer(web_server_api_url=WEB_SERVER_API_URL,
                  port=DHT_INDEXER_PORT,
                  node_id=DHT_INDEXER_NODE_ID,
                  bootstrap_node_address=DHT_INDEXER_BOOTSTRAP_ADDRESS)
