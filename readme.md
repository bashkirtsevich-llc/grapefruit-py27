# Grapefruit torrents search engine
## Overview
Bittorrent [DHT-network](https://en.wikipedia.org/wiki/Distributed_hash_table) crawler based on [kademlia](https://en.wikipedia.org/wiki/Kademlia) protocol. 

After bootstraping, service collect and ping all nodes in response queries thereby extend routing table.
When some outer node send request with torrent ```info_hash```(eg ```get_peers``` or ```announce```), service will store info in mongodb ```hashes``` collection.

When ```info_hash``` is received, service trying to find peers in bittorrent network and request torrent metadata such as torrent ```name```, torrent ```files``` and store into ```torrents``` collection.
## Requirements
Grapefruit required python libraries such as [```twisted matrix```](https://twistedmatrix.com/trac/) and ```pymongo```. Web-server required [```flask microframework```](http://flask.pocoo.org/).

You can use ```pip``` for install requirements:
```shell
pip install pymongo
pip install Twisted
pip install Flask
```
Thats all, I hope.

## Running
Grapefruit crawler can be run by executing ```start_grapefruit.sh```. Script will start MongoDB service and exec http server for comfortable navigation in torrents database. After starting you can open URL [http://localhost:8081/](http://localhost:8081/) and work with database.

Other files, such as ```start_dhtserver.sh``` and ```start_webserver.sh``` can be used for starting each service separatley.
### Configure services
In ```config.py``` file you can configure some server options, such as:
* MongoDB connection URL
* web server ip address (```0.0.0.0``` allows to access to server from network, ```127.0.0.1``` — access only from localhost) and port (default ```8081```, you can use other)
* dht-crawler port — is a outer DHT-crawler UDP port, whitch will be listen for incoming queries
* dht-server port — outer UDP port, whitch will be used for handling metadata loading

**Warning**, ```dht-crawler port``` should be differ from ```dht-server port```.
## MongoDB structure
### “torrents” collection
* Structure:
```json
{  
   "files":[  
      {  
         "path":[  
            "folder",
            "filename.ext"
         ],
         "length":123
      },

   ],
   "name":"torrent name",
   "info_hash":"0123456789abcdefabcd0123456789abcdefabcd"
}
```
* Full text wildcard index:
``` json
{  
   "v":2,
   "key":{  
      "_fts":"text",
      "_ftsx":1
   },
   "name":"$**_text",
   "ns":"grapefruit.torrents",
   "weights":{  
      "$**":1,
      "name":3,
      "path":2
   },
   "default_language":"english",
   "language_override":"language",
   "textIndexVersion":3
}                                      
```
### “crawler_route” collection
* Structure
```json
{  
   "routing_table":[  
      [  
         "0123456789abcdefabcd0123456789abcdefabcd",
         [  
            "1.2.3.4",
            5678
         ]
      ],
      [  
         "123456789abcdefabcd0123456789abcdefabcde",
         [  
            "9.10.11.12",
            1314
         ]
      ]
   ],
   "node_id":"23456789abcdefabcd0123456789abcdefabcdef"
}
```
This collection contains routing tables for spyder crawler. Using for quick bootstrap after startup.
### “hashes” collection
* Structure
```json
{  
   "timestamp":ISODate("2017-04-09..."),
   "info_hash":"0123456789abcdefabcd0123456789abcdefabcd"
}
```
This collection can be usefull for analytics.
## Internals
### “service” folder
#### Metadata loading
```service/metadata_loader.py``` — is a standalone bittorrent dht-server and simplified async torrent client, implements only extended handshake with “ut_metadata” extension. Based on [```twisted matrix```](https://twistedmatrix.com/trac/) python library.
Here is example, how to use ```metadata_loader``` standalone.
``` python
from metadata_loader import metadata_loader
from binascii import unhexlify


def print_metadata(metadata):
    print metadata


def on_bootstrap_done(search):
    search(unhexlify("0123456789abcdefabcd0123456789abcdefabcd"), print_metadata)


metadata_loader("router.bittorrent.com", 6881, 12346,
                on_bootstrap_done=on_bootstrap_done)
```
```router.bittorrent.com:6881``` — is a bootstrap node for initialization local routing table.
##### Bootstrap nodes
Known bittorrent bootstrap nodes:
* router.bittorrent.com:6881
* dht.transmissionbt.com:6881
* router.utorrent.com:6881