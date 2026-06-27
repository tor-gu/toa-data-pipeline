def generate_short_name(album, min_len, max_len):
    if len(album) <= max_len:
        return album
    for i in range(max_len - 1, min_len - 2, -1):
        if album[i] != " " and (i + 1 == len(album) or album[i + 1] == " "):
            return album[: i + 1]
    return album[:max_len]
