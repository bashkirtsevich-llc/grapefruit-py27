from config import *
from web.server import start_server

if __name__ == '__main__':
    start_server(mongodb_uri=MONGODB_URI,
                 host=WEB_SERVER_HOST,
                 port=WEB_SERVER_PORT,
                 api_access_host=WEB_SERVER_API_ACCESS_HOST)
