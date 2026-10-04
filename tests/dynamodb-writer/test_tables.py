import pandas as pd
from tables import (
    ALBUM_MATCHES_KEY,
    SCORES_KEY,
    Tables,
    Written,
    delete_all_stale,
    delete_stale,
    write_matches,
    write_scores,
    write_viz,
)
from toa.columns import ResultsCol, ScoresCol, VizCol
from transform import MATCHES_PK, VIZ_PK


class FakeBatch:
    def __init__(self, table):
        self.table = table

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def put_item(self, Item):  # noqa: N803 — boto3's spelling
        self.table.put_item(Item=Item)

    def delete_item(self, Key):  # noqa: N803
        self.table.delete_item(Key=Key)


class FakeTable:
    """Stands in for a boto3 Table: rows keyed by `key_names`, plus a record of
    every scan so tests can check the projection."""

    def __init__(self, key_names, rows=()):
        self.key_names = key_names
        self.rows = {}
        self.scans = []
        for row in rows:
            self.put_item(Item=row)

    def _key(self, item):
        return tuple(item[name] for name in self.key_names)

    def put_item(self, Item):  # noqa: N803
        self.rows[self._key(Item)] = Item

    def delete_item(self, Key):  # noqa: N803
        del self.rows[self._key(Key)]

    def batch_writer(self):
        return FakeBatch(self)

    def scan(self, ProjectionExpression, ExpressionAttributeNames):  # noqa: N803
        self.scans.append((ProjectionExpression, ExpressionAttributeNames))
        names = [
            ExpressionAttributeNames[a.strip()] for a in ProjectionExpression.split(",")
        ]
        return {"Items": [{n: row[n] for n in names} for row in self.rows.values()]}

    def query(self, **_kwargs):
        # Only write_viz queries, and the viz table holds one partition.
        return {"Items": [{"sk": row["sk"]} for row in self.rows.values()]}


def _scores(*ids, date="2024-01-01"):
    n = len(ids)
    return pd.DataFrame(
        {
            ScoresCol.ID: list(ids),
            ScoresCol.DATE: [date] * n,
            ScoresCol.SCORE: [1.0] * n,
            ScoresCol.ROBUSTNESS: [0.5] * n,
            ScoresCol.RANK: list(range(1, n + 1)),
        }
    )


# ── write_scores ────────────────────────────────────────────────────────────


def test_write_scores_returns_every_key_plus_metadata():
    table = FakeTable(SCORES_KEY)
    written = write_scores(table, _scores("a", "b"), {}, "2024-01-01")
    assert written == {
        ("a", "2024-01-01"),
        ("b", "2024-01-01"),
        ("METADATA", "latest_date"),
    }
    assert table.rows[("METADATA", "latest_date")]["value"] == "2024-01-01"


# ── write_matches ───────────────────────────────────────────────────────────


def test_write_matches_returns_both_key_sets():
    matches = FakeTable(("match_id",))
    album_matches = FakeTable(ALBUM_MATCHES_KEY)
    results = pd.DataFrame(
        {
            ResultsCol.MATCH_ID: ["m1"],
            ResultsCol.DATE: ["2024-01-01"],
            ResultsCol.ORDER: [["a", "b"]],
        }
    )
    match_keys, album_match_keys = write_matches(
        matches, album_matches, results, {}, {}
    )
    assert match_keys == {("m1",)}
    assert album_match_keys == {("a", "m1"), ("b", "m1")}
    stored = matches.rows[("m1",)]
    assert stored["gsi_pk"] == MATCHES_PK
    assert [entry["id"] for entry in stored["ranking"]] == ["a", "b"]


# ── delete_stale ────────────────────────────────────────────────────────────


def test_delete_stale_removes_only_unwritten_keys():
    table = FakeTable(
        SCORES_KEY,
        [
            {"id": "a", "date": "2024-01-01"},
            {"id": "gone", "date": "2024-01-01"},
            {"id": "METADATA", "date": "latest_date"},
        ],
    )
    written = {("a", "2024-01-01"), ("METADATA", "latest_date")}
    assert delete_stale(table, SCORES_KEY, written) == 1
    assert set(table.rows) == written


def test_delete_stale_aliases_reserved_words():
    # "date" and "key" are DynamoDB reserved words; neither may appear bare.
    table = FakeTable(SCORES_KEY)
    delete_stale(table, SCORES_KEY, set())
    projection, names = table.scans[0]
    assert projection == "#k0, #k1"
    assert names == {"#k0": "id", "#k1": "date"}


def test_delete_stale_full_write_keeps_metadata():
    table = FakeTable(SCORES_KEY, [{"id": "stale", "date": "2024-01-01"}])
    written = write_scores(table, _scores("a"), {}, "2024-01-01")
    delete_stale(table, SCORES_KEY, written)
    assert set(table.rows) == {("a", "2024-01-01"), ("METADATA", "latest_date")}


def test_delete_stale_nothing_to_delete():
    table = FakeTable(("match_id",), [{"match_id": "m1"}])
    assert delete_stale(table, ("match_id",), {("m1",)}) == 0
    assert set(table.rows) == {("m1",)}


# ── write_viz ───────────────────────────────────────────────────────────────


def test_write_viz_deletes_stale_sort_keys():
    table = FakeTable(("pk", "sk"), [{"pk": VIZ_PK, "sk": "ALBUM#gone"}])
    dates = pd.DataFrame({VizCol.DATE: ["2024-01-01"]})
    albums = pd.DataFrame(
        {
            VizCol.ID: ["a"],
            VizCol.DEBUT: [0],
            VizCol.SCORES: [[1.0]],
            VizCol.MATCH_IDS: [["m1"]],
        }
    )
    matches = pd.DataFrame(columns=[VizCol.MATCH_ID, VizCol.DATE, VizCol.ORDER])

    assert write_viz(table, dates, albums, matches, {}) == (2, 1)
    assert {sk for _, sk in table.rows} == {"DATES", "ALBUM#a"}


# ── delete_all_stale ────────────────────────────────────────────────────────


def test_delete_all_stale_counts_per_table():
    tables = Tables(
        scores=FakeTable(SCORES_KEY, [{"id": "x", "date": "d"}]),
        matches=FakeTable(("match_id",), [{"match_id": "m1"}, {"match_id": "m2"}]),
        album_matches=FakeTable(
            ALBUM_MATCHES_KEY, [{"album_id": "x", "match_id": "m2"}]
        ),
        global_statistics=FakeTable(("key",), [{"key": "num_albums"}]),
        viz=FakeTable(("pk", "sk")),
    )
    written = Written(matches={("m1",)}, global_statistics={("num_albums",)})
    assert delete_all_stale(tables, written) == {
        "scores": 1,
        "matches": 1,
        "album_matches": 1,
        "global_statistics": 0,
    }
