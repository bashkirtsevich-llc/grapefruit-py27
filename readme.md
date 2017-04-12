# Grapefruit torrents search engine
## Overview
Bittorrent [DHT-network](https://en.wikipedia.org/wiki/Distributed_hash_table) sniffer based on [kademlia](https://en.wikipedia.org/wiki/Kademlia) protocol. 

After bootstraping, service collect and ping all nodes in response queries thereby extend routing table.
When some outer node send request with torrent ```info_hash```(eg ```get_peers``` or ```announce```), service will store info in mongodb ```hashes``` collection.

When ```info_hash``` is received, service trying to find peers in bittorrent network and request torrent metadata such as torrent ```name```, torrent ```files``` and store into ```torrents``` collection.

## MongoDB structure
### “torrents” collection
* Structure:
```json
{
   "files":[
      {
         "path":[
            "folder", "filename.ext"
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
        "v" : 2,                         
        "key" : {                        
                "_fts" : "text",         
                "_ftsx" : 1              
        },                               
        "name" : "$**_text",             
        "ns" : "grapefruit.torrents",    
        "weights" : {                    
                "$**" : 1,               
                "name" : 3,              
                "path" : 2               
        },                               
        "default_language" : "english",  
        "language_override" : "language",
        "textIndexVersion" : 3           
}                                        
```
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