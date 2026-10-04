"""
Pure decisions behind a full rewrite: whether to do one, whether it is safe,
and which existing rows it leaves stale.
"""


def stale_keys(existing_keys, written_keys):
    """Keys in `existing_keys` that are absent from `written_keys`, sorted for a
    stable delete order. Keys may be strings or tuples, as long as both sides
    use the same shape."""
    return sorted(set(existing_keys) - set(written_keys))


def item_key(item, key_names):
    """The primary key of a DynamoDB item as a tuple, in `key_names` order."""
    return tuple(item[name] for name in key_names)


def rewrite_mode(rebuild, sentinel_present):
    """Why this run rewrites every table, or None for an incremental run.

    A manual rebuild and a pending rewrite sentinel do the same work, so the
    sentinel only matters when rebuild is off."""
    if rebuild:
        return "rebuild"
    if sentinel_present:
        return "sentinel"
    return None


def check_full_rewrite_inputs(results_count, scores_count):
    """Refuse a full rewrite from empty inputs.

    A full rewrite deletes every row the inputs do not contain, so a lost or
    truncated parquet would otherwise wipe the tables -- and the run would
    still succeed."""
    if results_count == 0 or scores_count == 0:
        raise ValueError(
            f"refusing full rewrite from empty inputs: {results_count} results, "
            f"{scores_count} scores"
        )
