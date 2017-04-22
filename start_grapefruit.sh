sudo service mongod start
python web_server.py &
python dht_crawler.py &
python dht_indexer.py &