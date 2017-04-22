from config import *
from service.crawler import start_crawler

if __name__ == '__main__':
    start_crawler(mongodb_uri=MONGODB_URI,
                  port=DHT_CRAWLER_PORT,
                  node_id=DHT_CRAWLER_NODE_ID)
