use grapefruit

// rename collection
db.torrents.renameCollection("torrents_old")

// unset "attempt" field
db.torrents_old.find({"attempt": {$exists: true}}).forEach(function(doc) {
    db.torrents_old.update({"info_hash": doc.info_hash}, {$unset: {"attempt": ""}})
})

// recreate "torrents" collection, insert torrents with metadata only
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

// drop "torrents_old" collection
db.torrents_old.drop()

// add lost torrents from "hashes"
db.hashes.distinct("info_hash").forEach(function(info_hash) {
    if (db.torrents.count({"info_hash": info_hash}) == 0)
        db.torrents.insert({"info_hash": info_hash})
})
