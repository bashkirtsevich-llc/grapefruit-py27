from web.web_server import start_web_server
from web_server_config import *

if __name__ == '__main__':
    start_web_server(
        mongodb_uri=MONGODB_URI,
        host=WEB_SERVER_HOST,
        port=WEB_SERVER_PORT
    )
