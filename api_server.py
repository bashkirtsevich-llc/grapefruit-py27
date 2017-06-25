from web.api_server import start_api_server
from api_server_config import *

if __name__ == '__main__':
    start_api_server(
        mongodb_uri=MONGODB_URI,
        host=API_SERVER_HOST,
        port=API_SERVER_PORT
    )
