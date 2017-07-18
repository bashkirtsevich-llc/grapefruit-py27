use grapefruit

// rename collection
db.hashes.renameCollection("hashes_old")

// fill "hashes" collection by "torrents" collection
db.torrents.find().forEach(function(doc){
    db.hashes.insert({
        "info_hash": doc.info_hash,
        "access_count": NumberInt("access_count" in doc ? doc.access_count : 0),
        "loaded": "name" in doc
    })
})

// include hashes skipped in torrents
db.hashes_old.distinct("info_hash").forEach(function (info_hash) {
    if (db.torrents.count({"info_hash": info_hash}) == 0)
        db.hashes.insert({
            "info_hash": info_hash,
            "access_count": NumberInt(0),
            "loaded": false
        })
})

// create indexes
db.hashes.createIndex({"info_hash": 1}, {name: "info_hash", unique: true})
db.hashes.createIndex({"access_count": 1}, {name: "access_count"})
db.hashes.createIndex({"loaded": 1}, {name: "loaded"})

// drop old collection
db.hashes_old.drop()

// remove unloaded torrents from "torrents" collection
db.torrents.remove({"name": {$exists: false}})

// unset "access_count" field in "torrents" collection
db.torrents.find().forEach(function(doc){
    db.torrents.update({"info_hash": doc.info_hash}, {$unset: {"access_count": ""}})
})
