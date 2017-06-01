from binascii import hexlify, unhexlify
import requests
from dht.common_utils import generate_node_id
from dht.crawler.krpc import DHTProtocol


def __try_load_routing_table(web_server_api_url, local_node_host, local_node_port, local_node_id=None):
    response = requests.get(
        "{0}/load_routing_table".format(web_server_api_url),
        params={"local_node_host": local_node_host,
                "local_node_port": local_node_port,
                "local_node_id": local_node_id}
    ).json()

    # if "code" in response["result"]:
    result = response.get("result", None)

    if result and all(map(lambda k: k in result,
                          ("buckets", "local_node_host", "local_node_port", "local_node_id"))):
        table = result

        # We must unhexlify all identifiers
        node_id = unhexlify(table["local_node_id"])
        buckets = map(
            lambda bucket: map(
                lambda node: [
                    unhexlify(node[0]),  # node id (hex)
                    node[1]],  # node address tuple (host, port)
                bucket),
            table["buckets"])

        # Restore routing table
        return {
            "buckets": buckets,
            "local_node_host": table["local_node_host"],
            "local_node_port": table["local_node_port"],
            "local_node_id": node_id
        }
    else:
        # Generate empty routing table
        return {
            "buckets": [],
            "local_node_host": local_node_host,
            "local_node_port": local_node_port,
            "local_node_id": local_node_id if local_node_id else generate_node_id()
        }


def __store_routing_table(web_server_api_url, local_node_id, address, buckets):
    try:
        node_id_hex = hexlify(local_node_id)
        buckets_hex = map(
            lambda bucket: map(
                lambda node: [
                    hexlify(node[0]),  # node id (hex)
                    node[1]],  # node address tuple (host, port)
                bucket),
            buckets)

        requests.post(
            "{0}/store_routing_table".format(web_server_api_url),
            data={"buckets": buckets_hex,
                  "local_node_id": node_id_hex,
                  "local_node_host": address[0],
                  "local_node_port": address[1]}
        )
    except:
        print "__store_routing_table error"


def __store_info_hash(web_server_api_url, info_hash):
    try:
        requests.post("{0}/add_torrent".format(web_server_api_url),
                      data={"info_hash": hexlify(info_hash)})
    except:
        print "__store_info_hash error"


def start_crawler(web_server_api_url, port, node_id=None):
    routing_table = __try_load_routing_table(web_server_api_url, "0.0.0.0", port, node_id)

    arguments = {
        "node_id": routing_table["local_node_id"],
        "routing_table": routing_table["buckets"],
        "address": (routing_table["local_node_host"],
                    routing_table["local_node_port"]),
        "on_save_routing_table":
            lambda local_node_id, routing_table, address:
            __store_routing_table(web_server_api_url, local_node_id, address, routing_table),
        "on_get_peers":
            lambda info_hash:
            __store_info_hash(web_server_api_url, info_hash),
        "on_announce":
            lambda info_hash, announce_host, announce_port:
            __store_info_hash(web_server_api_url, info_hash)
    }

    protocol = DHTProtocol(**arguments)
    protocol.start()
