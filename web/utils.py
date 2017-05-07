def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)

        num /= 1024.0

    return "%.1f %s%s" % (num, "Y", suffix)


def get_files_list(files, first_ten=False):
    return map(lambda f: {"name": reduce(lambda r, e: r + ("/" if r else "") + e, f["path"], ""),
                          "size": sizeof_fmt(f["length"])}, files[:10] if first_ten else files)


def get_files_size(files):
    return sizeof_fmt(reduce(lambda r, e: r + e["length"], files, 0))
