## MongoDB "torrents" collection structure
```json
{
   "files":[
      {
         "path":[
            "folder", "filename.ext"
         ],
         "length":123
      },
      ...
   ],
   "name":"torrent name",
   "info_hash":"0123456789abcdefabcd0123456789abcdefabcd"
}
```

## Metadata loading
metadata_loader.py
``` python
from binascii import hexlify, unhexlify


def print_metadata(metadata):
    print metadata


def on_bootstrap_done(search):
    search(unhexlify("0123456789abcdefabcd0123456789abcdefabcd"), print_metadata)


metadata_loader("router.bittorrent.com", 6881, 12346, on_bootstrap_done=on_bootstrap_done)
```