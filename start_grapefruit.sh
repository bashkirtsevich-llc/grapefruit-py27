echo "start web server"
python web_server.py &
echo "wait 30 seconds"
sleep 30
echo "start crawler"
python dht_crawler.py &
echo "start indexer"
python dht_indexer.py &