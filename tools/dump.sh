rm -r dump
mongodump
rm database.tar.gz
tar -czvf database.tar.gz dump
rm -r dump
