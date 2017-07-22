db.torrents.createIndex({"name": 1}, {name: "name"})

db.torrents.find().sort({"name": 1}).forEach(function(doc){
    print("magnet:?xt=urn:btih:" + doc.info_hash, doc.name)
})