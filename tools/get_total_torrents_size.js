size = db.torrents.find({"files": {$exists: true}}).toArray().reduce(
    function(total, doc) {
        return total + doc.files.reduce(
            function(total, item) {
                return total + item.length
            }, 0)
    }, 0)

print(size)