db.torrents.find().toArray.forEach(function(doc){
    size = doc.files.reduce(function(total, item) {
        return total + item.length
    }, 0)
    print(doc.info_hash, size)
})
