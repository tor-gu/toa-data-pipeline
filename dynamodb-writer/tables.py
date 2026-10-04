"""Every DynamoDB write and delete the writer makes.

Functions take `Table` objects rather than names, so tests can pass fakes. They
return what they wrote or deleted, and leave logging to the handler.
"""

from dataclasses import dataclass, field

from boto3.dynamodb.conditions import Key
from rewrite import item_key, stale_keys
from toa.columns import ResultsCol, ScoresCol, VizCol
from toa.dynamodb import query_all, scan_all
from transform import (
    VIZ_PK,
    album_match_item,
    build_scores_lookup,
    match_item,
    ranking_entry,
    score_item,
    statistics_items,
    viz_album_item,
    viz_dates_item,
    viz_match_item,
)

# Primary key attribute names, in item_key order.
SCORES_KEY = ("id", "date")
MATCHES_KEY = ("match_id",)
ALBUM_MATCHES_KEY = ("album_id", "match_id")
STATISTICS_KEY = ("key",)


@dataclass
class Tables:
    scores: object
    matches: object
    album_matches: object
    global_statistics: object
    viz: object


@dataclass
class Written:
    """The keys each table received, and the viz rewrite's own counts."""

    scores: set = field(default_factory=set)
    matches: set = field(default_factory=set)
    album_matches: set = field(default_factory=set)
    global_statistics: set = field(default_factory=set)
    viz_items: int = 0
    viz_stale_deleted: int = 0


def write_scores(table, affected_scores, names, latest_date):
    """Returns the key of every item written."""
    written = set()
    with table.batch_writer() as batch:
        for _, row in affected_scores.iterrows():
            name = names.get(row[ScoresCol.ID], {})
            item = score_item(row, name)
            batch.put_item(Item=item)
            written.add(item_key(item, SCORES_KEY))
    metadata = {"id": "METADATA", "date": "latest_date", "value": latest_date}
    table.put_item(Item=metadata)
    written.add(item_key(metadata, SCORES_KEY))
    return written


def write_matches(
    matches_table, album_matches_table, affected_results, names, scores_lookup
):
    """Returns the keys written to each table, as (matches, album_matches)."""
    match_keys = set()
    album_match_keys = set()
    with (
        matches_table.batch_writer() as matches_batch,
        album_matches_table.batch_writer() as album_matches_batch,
    ):
        for _, row in affected_results.iterrows():
            match_id = row[ResultsCol.MATCH_ID]
            date = row[ResultsCol.DATE]
            order = row[ResultsCol.ORDER]

            ranking = [
                ranking_entry(i, album_id, date, names, scores_lookup)
                for i, album_id in enumerate(order)
            ]
            matches_batch.put_item(Item=match_item(match_id, date, ranking))
            match_keys.add((match_id,))

            for album_id in order:
                name = names.get(album_id, {})
                album_matches_batch.put_item(
                    Item=album_match_item(album_id, match_id, date, name)
                )
                album_match_keys.add((album_id, match_id))
    return match_keys, album_match_keys


def write_statistics(table, stats_df):
    """Returns the key of every item written."""
    written = set()
    with table.batch_writer() as batch:
        for item in statistics_items(stats_df.iloc[0]):
            batch.put_item(Item=item)
            written.add(item_key(item, STATISTICS_KEY))
    return written


# The viz dataset is always fully rewritten (never earliest_date-filtered):
# a new date lengthens every album's score vector, and the identity of the
# largest component can change between runs.
def write_viz(table, dates_df, albums_df, matches_df, names):
    """Returns (items written, stale items deleted)."""
    dates = list(dates_df[VizCol.DATE])
    items = [viz_dates_item(dates, len(albums_df), len(matches_df))]
    for _, row in albums_df.iterrows():
        items.append(viz_album_item(row, names.get(row[VizCol.ID], {})))
    for _, row in matches_df.iterrows():
        items.append(viz_match_item(row))

    existing = query_all(
        table,
        KeyConditionExpression=Key("pk").eq(VIZ_PK),
        ProjectionExpression="sk",
    )
    stale = stale_keys(
        (item["sk"] for item in existing), (item["sk"] for item in items)
    )

    # Write before deleting so concurrent readers never see an empty partition.
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
        for sk in stale:
            batch.delete_item(Key={"pk": VIZ_PK, "sk": sk})

    return len(items), len(stale)


def write_all(tables, inputs, affected_scores, affected_results):
    """Write every table from `inputs`, in a fixed order. Returns a `Written`."""
    written = Written()
    latest_date = inputs.scores[ScoresCol.DATE].max()
    written.scores = write_scores(
        tables.scores, affected_scores, inputs.names, latest_date
    )
    written.matches, written.album_matches = write_matches(
        tables.matches,
        tables.album_matches,
        affected_results,
        inputs.names,
        build_scores_lookup(affected_scores),
    )
    written.global_statistics = write_statistics(
        tables.global_statistics, inputs.statistics
    )
    written.viz_items, written.viz_stale_deleted = write_viz(
        tables.viz,
        inputs.viz_dates,
        inputs.viz_albums,
        inputs.viz_matches,
        inputs.names,
    )
    return written


def delete_stale(table, key_names, written_keys):
    """Delete every row of `table` whose key was not just written. Only safe after
    a full write, where `written_keys` covers everything that should exist."""
    # Aliases throughout: "date" and "key" are DynamoDB reserved words.
    aliases = {f"#k{i}": name for i, name in enumerate(key_names)}
    existing = scan_all(
        table,
        ProjectionExpression=", ".join(aliases),
        ExpressionAttributeNames=aliases,
    )
    stale = stale_keys((item_key(item, key_names) for item in existing), written_keys)
    with table.batch_writer() as batch:
        for key in stale:
            batch.delete_item(Key=dict(zip(key_names, key)))
    return len(stale)


def delete_all_stale(tables, written):
    """Delete, from every table, the rows a full write did not touch. Returns the
    count per table.

    Call only after write_all has finished every table, for the same reason
    write_viz deletes last: readers never see a gap. viz is not listed because
    write_viz already deleted its own stale rows."""
    return {
        "scores": delete_stale(tables.scores, SCORES_KEY, written.scores),
        "matches": delete_stale(tables.matches, MATCHES_KEY, written.matches),
        "album_matches": delete_stale(
            tables.album_matches, ALBUM_MATCHES_KEY, written.album_matches
        ),
        "global_statistics": delete_stale(
            tables.global_statistics, STATISTICS_KEY, written.global_statistics
        ),
    }
