from config import *
from service.server import start_server

if __name__ == '__main__':
    start_server(mongodb_uri=MONGODB_URI,
                 crawler_port=DHT_CRAWLER_PORT,
                 server_port=DHT_SERVER_PORT,
                 crawler_node_id=DHT_CRAWLER_NODE_ID,
                 server_node_id=DHT_SERVER_NODE_ID)
