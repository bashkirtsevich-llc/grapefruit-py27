# Grapefruit torrents search engine
## Overview
Bittorrent [DHT-network](https://en.wikipedia.org/wiki/Distributed_hash_table) crawler based on [kademlia](https://en.wikipedia.org/wiki/Kademlia) protocol. 

After bootstraping, service collect and ping all nodes in response queries thereby extend routing table.
When some outer node send request with torrent ```info_hash```(eg ```get_peers``` or ```announce```), service will store info in mongodb ```hashes``` collection.

When ```info_hash``` is received, service trying to find peers in bittorrent network and request torrent metadata such as torrent ```name```, torrent ```files``` and store into ```torrents``` collection.
## Requirements
Grapefruit required python libraries such as [```twisted matrix```](https://twistedmatrix.com/trac/) and ```pymongo```. Web-server required [```flask microframework```](http://flask.pocoo.org/).

You can use ```pip``` for install requirements (```pip install -r requirements.txt```).
Actual requirements (from ```requirements.txt```):
```
flask==0.11.1
pymongo==3.3.1
twisted==16.6.0
rpcudp==2.1
bencode==1.0
zope.interface==4.3.3
```
Requirement packets for successfully install ```twisted```:
```
sudo apt-get install build-essential autoconf libtool pkg-config python-opengl python-imaging python-pyrex python-pyside.qtopengl idle-python2.7 qt4-dev-tools qt4-designer libqtgui4 libqtcore4 libqt4-xml libqt4-test libqt4-script libqt4-network libqt4-dbus python-qt4 python-qt4-gl libgle3 python-dev
```
Or `python-dev` only:
```
sudo apt-get install python-dev
```
Thats all, I hope.

## Running
Grapefruit crawler can be run by executing ```start_grapefruit.sh```. Script will start MongoDB service and exec http server for comfortable navigation in torrents database. After starting you can open URL [http://localhost:8081/](http://localhost:8081/) and work with database.

Other files, such as `start_dhtserver.sh` and `start_webserver.sh` can be used for starting each service separatley.
### Configure services
In `web_server_config.py` file you can configure some server options, such as:
* MongoDB connection URL
* web server ip address (```0.0.0.0``` allows to access to server from network, ```127.0.0.1``` — access only from localhost) and port (default ```8081```, you can use other)
* `dht_crawler_config.py`:
```python
WEB_SERVER_API_URL = "http://127.0.0.1:8081/api"

DHT_CRAWLER_NODES_INFO = map(lambda port: {"port": port, "node_id": None},
                             xrange(6981, 6991))
```
`xrange(6981, 6991)` — is a outer DHT-crawler UDP port, whitch will be listen for incoming queries
* `dht_indexer_config.py`:
```python
WEB_SERVER_API_URL = "http://127.0.0.1:8081/api"

DHT_DEFAULT_BOOTSTRAP_ADDRESS = ("router.bittorrent.com", 6881)

DHT_INDEXERS_INFO = map(lambda port: {"port": port,
                                      "node_id": None,
                                      "bootstrap": DHT_DEFAULT_BOOTSTRAP_ADDRESS},
                        xrange(6881, 6882))
```
`xrange(6881, 6882)` — outer UDP port, whitch will be used for handling metadata loading

**Warning**, ```dht-crawler port``` should be differ from ```dht-server port```.
## MongoDB structure
### “torrents” collection
* Structure:
```json
{  
   "files":[  
      {  
         "path":[  
            "folder1",
            "file1"
         ],
         "length":10
      },
      {  
         "path":[  
            "folder2",
            "file2"
         ],
         "length":20
      }
   ],
   "name":"sample torrent",
   "info_hash":"7752b63e7b62f3f13d4a070a0522196e7142fbe6"
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
   "name":"fulltext_index",
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
         "0bfea6427313a84144d2eca74e57689155c379f4",
         [  
            "1.2.3.4",
            5678
         ]
      ],
      [  
         "39e0da6b7609a3f225e86aa55175dd85d193e121",
         [  
            "9.10.11.12",
            1314
         ]
      ]
   ],
   "node_id":"20b15ed501c738dab5d96abe0f22a44e1de75b9a"
}
```
This collection contains routing tables for spyder crawler. Using for quick bootstrap after startup.
### “hashes” collection
* Structure
```json
{  
   "timestamp" : ISODate("2017-04-28T16:11:52.405Z"),
   "info_hash" : "20b15ed501c738dab5d96abe0f22a44e1de75b9a"
}
```
This collection can be usefull for analytics.
## Database migration
For migrate from older database to newest, you can execute `tools/migrate_from_1.3.js` script is mongo shell.
### Manual migration.
Switch to database:
```javascript
use grapefruit
```
Rename `torrents` collection:
```javascript
db.torrents.renameCollection("torrents_old")
```
Unset `attempt` field:
```javascript
db.torrents_old.find({"attempt": {$exists: true}}).forEach(function(doc) {
    db.torrents_old.update({"info_hash": doc.info_hash}, {$unset: {"attempt": ""}})
})
```
Recreate `torrents` collection, insert torrents with metadata only:
```javascript
db.torrents_old.find({$and: [{"name": {$exists: true}}, {"files": {$exists: true}}]}).forEach(function(doc) {
    cursor = db.hashes.aggregate([
        {$match: {"info_hash": doc.info_hash}},
        {$group: {_id: "$info_hash", timestamp: {$min: "$timestamp"}}}
    ]).toArray()
        
    if (cursor.length > 0)
        timestamp = cursor[0].timestamp
    else
        timestamp = ISODate("2017-01-01 00:00:00")

    db.torrents.insert({"info_hash": doc.info_hash, "name": doc.name, "files": doc.files, "timestamp": timestamp})
})
```
Drop `torrents_old` collection:
```javascript
db.torrents_old.drop()
```
Add lost torrents from `hashes` collection:
```javascript
db.hashes.distinct("info_hash").forEach(function(info_hash) {
    if (db.torrents.count({"info_hash": info_hash}) == 0)
        db.torrents.insert({"info_hash": info_hash})
})

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