import threading
import time
from datetime import date, timedelta

import pandas as pd
import pytest
from toa.columns import ScoresCol
from update import (
    CHUNK_SIZE,
    assemble_updated_scores,
    chunk_dates,
    score_chunk,
    score_dates,
    select_dates_to_rescore,
    select_scores_to_keep,
)

DATES = ["2024-01-01", "2024-02-01", "2024-03-01"]


def make_dates(n):
    """`n` consecutive dates, ascending -- enough to span several chunks."""
    start = date(2024, 1, 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def make_scores_df(rows):
    return pd.DataFrame(
        rows,
        columns=[ScoresCol.ID, ScoresCol.SCORE, ScoresCol.ROBUSTNESS, ScoresCol.DATE],
    )


def empty_scores_df():
    return make_scores_df([])


# ── select_dates_to_rescore ────────────────────────────────────────────────────


def test_select_dates_from_the_middle():
    assert select_dates_to_rescore(DATES, "2024-02-01", False) == DATES[1:]


def test_select_dates_includes_earliest_date_itself():
    # the date a match was added is refitted too, not just the ones after it
    assert "2024-02-01" in select_dates_to_rescore(DATES, "2024-02-01", False)


def test_select_dates_earliest_before_all_dates():
    assert select_dates_to_rescore(DATES, "2023-01-01", False) == DATES


def test_select_dates_earliest_after_all_dates():
    assert select_dates_to_rescore(DATES, "2025-01-01", False) == []


def test_select_dates_earliest_between_dates():
    assert select_dates_to_rescore(DATES, "2024-01-15", False) == DATES[1:]


def test_select_dates_no_result_dates():
    assert select_dates_to_rescore([], "2024-01-01", False) == []


def test_select_dates_rebuild_covers_everything():
    assert select_dates_to_rescore(DATES, "2024-03-01", True) == DATES


def test_select_dates_rebuild_ignores_null_earliest_date():
    assert select_dates_to_rescore(DATES, None, True) == DATES


def test_select_dates_rebuild_with_no_result_dates():
    assert select_dates_to_rescore([], None, True) == []


def test_select_dates_rebuild_does_not_alias_input():
    result_dates = list(DATES)
    selected = select_dates_to_rescore(result_dates, None, True)
    selected.append("2024-04-01")
    assert result_dates == DATES


# ── select_scores_to_keep ──────────────────────────────────────────────────────


def test_select_scores_keeps_only_earlier_dates():
    scores = make_scores_df(
        [
            ("a", 1.0, 0.5, "2024-01-01"),
            ("b", 2.0, 0.5, "2024-02-01"),
            ("c", 3.0, 0.5, "2024-03-01"),
        ]
    )
    kept = select_scores_to_keep(scores, "2024-02-01", False)
    assert kept[ScoresCol.DATE].tolist() == ["2024-01-01"]


def test_select_scores_keeps_nothing_when_earliest_is_first_date():
    scores = make_scores_df([("a", 1.0, 0.5, "2024-01-01")])
    assert select_scores_to_keep(scores, "2024-01-01", False).empty


def test_select_scores_keeps_everything_when_earliest_is_later():
    scores = make_scores_df(
        [
            ("a", 1.0, 0.5, "2024-01-01"),
            ("b", 2.0, 0.5, "2024-02-01"),
        ]
    )
    kept = select_scores_to_keep(scores, "2024-03-01", False)
    assert len(kept) == 2


def test_select_scores_on_empty_frame():
    kept = select_scores_to_keep(empty_scores_df(), "2024-01-01", False)
    assert kept.empty
    assert list(kept.columns) == [
        ScoresCol.ID,
        ScoresCol.SCORE,
        ScoresCol.ROBUSTNESS,
        ScoresCol.DATE,
    ]


def test_select_scores_rebuild_keeps_nothing():
    scores = make_scores_df(
        [
            ("a", 1.0, 0.5, "2024-01-01"),
            ("b", 2.0, 0.5, "2024-02-01"),
        ]
    )
    kept = select_scores_to_keep(scores, "2024-03-01", True)
    assert kept.empty


def test_select_scores_rebuild_preserves_columns():
    scores = make_scores_df([("a", 1.0, 0.5, "2024-01-01")])
    kept = select_scores_to_keep(scores, None, True)
    assert list(kept.columns) == list(scores.columns)


def test_select_scores_does_not_mutate_input():
    scores = make_scores_df(
        [
            ("a", 1.0, 0.5, "2024-01-01"),
            ("b", 2.0, 0.5, "2024-02-01"),
        ]
    )
    select_scores_to_keep(scores, "2024-02-01", False)
    select_scores_to_keep(scores, None, True)
    assert len(scores) == 2


# ── score_dates ────────────────────────────────────────────────────────────────


DATE_ORDER = [date for date in DATES for _ in range(2)]


def fake_score_one(date, seed=None):
    """Two rows per date, stamped with it, as the real per-date fit returns."""
    return [
        {ScoresCol.ID: "a", ScoresCol.SCORE: 1.0, ScoresCol.DATE: date},
        {ScoresCol.ID: "b", ScoresCol.SCORE: 2.0, ScoresCol.DATE: date},
    ]


class InFlightCounter:
    """A fake fit that records the high-water mark of concurrent calls."""

    def __init__(self, delay=0.05):
        self.delay = delay
        self.lock = threading.Lock()
        self.current = 0
        self.max_seen = 0

    def __call__(self, date, seed=None):
        with self.lock:
            self.current += 1
            self.max_seen = max(self.max_seen, self.current)
        time.sleep(self.delay)
        with self.lock:
            self.current -= 1
        return fake_score_one(date)


class SeedRecorder:
    """A fake fit that records the seed each date was given.

    Each date returns its own distinctive scores, so a recorded seed identifies
    exactly which date it came from.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.seeds = {}

    def __call__(self, date, seed=None):
        with self.lock:
            self.seeds[date] = seed
        return [
            {ScoresCol.ID: "a", ScoresCol.SCORE: date, ScoresCol.ROBUSTNESS: 0.5},
            {ScoresCol.ID: "b", ScoresCol.SCORE: date, ScoresCol.ROBUSTNESS: 0.5},
        ]

    def seeded_from(self, date):
        """The date whose fit seeded `date`, or None if it started cold."""
        seed = self.seeds[date]
        return None if seed is None else seed[0][ScoresCol.SCORE]


def test_score_dates_serially_returns_rows_in_date_order():
    rows = score_dates(DATES, fake_score_one, 1)
    assert [row[ScoresCol.DATE] for row in rows] == DATE_ORDER


def test_score_dates_in_parallel_returns_rows_in_date_order():
    # each date sleeps less than the one before it, so the fits finish in the
    # reverse of the order they were submitted -- the result must not follow
    dates = make_dates(CHUNK_SIZE * 3)
    delays = {d: 0.01 * (len(dates) - i) for i, d in enumerate(dates)}

    def slow_score_one(d, seed=None):
        time.sleep(delays[d])
        return fake_score_one(d)

    rows = score_dates(dates, slow_score_one, 4)
    assert [row[ScoresCol.DATE] for row in rows] == [d for d in dates for _ in range(2)]


def test_score_dates_serially_fits_each_date_once():
    calls = []

    def record(date, seed=None):
        calls.append(date)
        return []

    score_dates(DATES, record, 1)
    assert calls == DATES


def test_score_dates_in_parallel_fits_each_date_once():
    calls = []
    lock = threading.Lock()

    def record(date, seed=None):
        with lock:
            calls.append(date)
        return []

    score_dates(DATES, record, 4)
    assert sorted(calls) == DATES


def test_score_dates_serially_runs_one_fit_at_a_time():
    counter = InFlightCounter()
    score_dates(DATES, counter, 1)
    assert counter.max_seen == 1


def test_score_dates_in_parallel_overlaps_fits():
    # chunks are what run in parallel, so this needs more than one of them
    counter = InFlightCounter(delay=0.01)
    score_dates(make_dates(CHUNK_SIZE * 4), counter, 4)
    assert counter.max_seen > 1


def test_score_dates_caps_concurrency_at_num_executors():
    counter = InFlightCounter(delay=0.01)
    score_dates(make_dates(CHUNK_SIZE * 4), counter, 2)
    assert counter.max_seen <= 2


def test_score_dates_within_a_chunk_runs_one_fit_at_a_time():
    """A chained fit has to wait for the seed it is given."""
    counter = InFlightCounter(delay=0.01)
    score_dates(make_dates(CHUNK_SIZE), counter, 8)
    assert counter.max_seen == 1


def test_score_dates_below_one_executor_runs_serially():
    counter = InFlightCounter()
    score_dates(DATES, counter, 0)
    assert counter.max_seen == 1


def test_score_dates_with_no_dates():
    assert score_dates([], fake_score_one, 4) == []


def test_score_dates_serially_propagates_failure():
    def failing(date, seed=None):
        raise RuntimeError("Score Lambda error")

    with pytest.raises(RuntimeError):
        score_dates(DATES, failing, 1)


def test_score_dates_in_parallel_propagates_failure():
    def failing(date, seed=None):
        raise RuntimeError("Score Lambda error")

    with pytest.raises(RuntimeError):
        score_dates(DATES, failing, 4)


# ── chunk_dates ────────────────────────────────────────────────────────────────


def test_chunk_dates_with_no_dates():
    assert chunk_dates([]) == []


def test_chunk_dates_short_list_is_one_chunk():
    assert chunk_dates(DATES) == [DATES]


def test_chunk_dates_exactly_one_chunk_full():
    dates = make_dates(CHUNK_SIZE)
    assert chunk_dates(dates) == [dates]


def test_chunk_dates_splits_at_chunk_size():
    dates = make_dates(CHUNK_SIZE + 1)
    assert chunk_dates(dates) == [dates[:CHUNK_SIZE], dates[CHUNK_SIZE:]]


@pytest.mark.parametrize("n", [1, 7, CHUNK_SIZE, CHUNK_SIZE * 3, CHUNK_SIZE * 5 + 3])
def test_chunk_dates_covers_every_date_in_order(n):
    dates = make_dates(n)
    assert [d for chunk in chunk_dates(dates) for d in chunk] == dates


@pytest.mark.parametrize("n", [1, 7, CHUNK_SIZE, CHUNK_SIZE * 3, CHUNK_SIZE * 5 + 3])
def test_chunk_dates_chunks_are_never_empty_or_oversized(n):
    chunks = chunk_dates(make_dates(n))
    assert all(0 < len(chunk) <= CHUNK_SIZE for chunk in chunks)


def test_chunk_dates_does_not_depend_on_anything_but_the_dates():
    """The whole point: the split is a function of the dates alone."""
    dates = make_dates(CHUNK_SIZE * 3 + 5)
    assert chunk_dates(dates) == chunk_dates(list(dates))


# ── score_chunk ────────────────────────────────────────────────────────────────


def test_score_chunk_head_starts_cold():
    recorder = SeedRecorder()
    score_chunk(DATES, recorder)
    assert recorder.seeds[DATES[0]] is None


def test_score_chunk_chains_each_date_to_the_one_before():
    recorder = SeedRecorder()
    score_chunk(DATES, recorder)
    assert recorder.seeded_from(DATES[1]) == DATES[0]
    assert recorder.seeded_from(DATES[2]) == DATES[1]


def test_score_chunk_seed_carries_only_id_and_score():
    """robustness and date are dead weight in the payload."""
    recorder = SeedRecorder()
    score_chunk(DATES, recorder)
    seed = recorder.seeds[DATES[1]]
    assert all(set(row) == {ScoresCol.ID, ScoresCol.SCORE} for row in seed)


def test_score_chunk_seeds_every_album():
    recorder = SeedRecorder()
    score_chunk(DATES, recorder)
    assert [row[ScoresCol.ID] for row in recorder.seeds[DATES[1]]] == ["a", "b"]


def test_score_chunk_returns_rows_in_order():
    rows = score_chunk(DATES, fake_score_one)
    assert [row[ScoresCol.DATE] for row in rows] == DATE_ORDER


def test_score_chunk_with_no_dates():
    assert score_chunk([], fake_score_one) == []


def test_score_chunk_propagates_failure():
    def failing(date, seed=None):
        raise RuntimeError("Score Lambda error")

    with pytest.raises(RuntimeError):
        score_chunk(DATES, failing)


# ── seeding through score_dates ────────────────────────────────────────────────


def test_score_dates_seeds_from_the_previous_date():
    recorder = SeedRecorder()
    dates = make_dates(CHUNK_SIZE)
    score_dates(dates, recorder, 1)
    assert [recorder.seeded_from(d) for d in dates] == [None] + dates[:-1]


def test_score_dates_does_not_chain_across_chunks():
    """Every chunk head is cold, whatever finished before it."""
    recorder = SeedRecorder()
    dates = make_dates(CHUNK_SIZE * 3)
    score_dates(dates, recorder, 4)
    for chunk in chunk_dates(dates):
        assert recorder.seeded_from(chunk[0]) is None


@pytest.mark.parametrize("num_executors", [1, 2, 8])
def test_score_dates_seeds_do_not_depend_on_num_executors(num_executors):
    """The property the chunking exists for.

    A warm start moves the fit by a hair, so if the seeds shifted with the
    executor count, the same rebuild run two ways would write different scores.
    """
    dates = make_dates(CHUNK_SIZE * 3 + 7)
    serial = SeedRecorder()
    score_dates(dates, serial, 1)

    parallel = SeedRecorder()
    score_dates(dates, parallel, num_executors)

    assert parallel.seeds == serial.seeds


# ── assemble_updated_scores ────────────────────────────────────────────────────


NEW_ROWS = [
    {
        ScoresCol.ID: "b",
        ScoresCol.SCORE: 2.0,
        ScoresCol.ROBUSTNESS: 0.5,
        ScoresCol.DATE: "2024-02-01",
    },
    {
        ScoresCol.ID: "c",
        ScoresCol.SCORE: 3.0,
        ScoresCol.ROBUSTNESS: 0.5,
        ScoresCol.DATE: "2024-02-01",
    },
]


def test_assemble_concatenates_kept_and_new():
    kept = make_scores_df([("a", 1.0, 0.5, "2024-01-01")])
    updated = assemble_updated_scores(kept, NEW_ROWS)
    assert len(updated) == 3
    assert updated[ScoresCol.ID].tolist() == ["a", "b", "c"]
    assert updated[ScoresCol.DATE].tolist() == [
        "2024-01-01",
        "2024-02-01",
        "2024-02-01",
    ]


def test_assemble_reindexes():
    kept = make_scores_df(
        [
            ("a", 1.0, 0.5, "2024-01-01"),
            ("b", 2.0, 0.5, "2024-01-01"),
        ]
    ).iloc[1:]
    updated = assemble_updated_scores(kept, NEW_ROWS)
    assert updated.index.tolist() == [0, 1, 2]


def test_assemble_with_nothing_kept():
    # the rebuild / cold-start path -- the result is just the new rows
    updated = assemble_updated_scores(empty_scores_df(), NEW_ROWS)
    assert len(updated) == 2
    assert updated[ScoresCol.ID].tolist() == ["b", "c"]


def test_assemble_with_nothing_kept_has_no_null_rows():
    updated = assemble_updated_scores(empty_scores_df(), NEW_ROWS)
    assert not updated.isna().any().any()


def test_assemble_with_no_new_rows_returns_kept():
    kept = make_scores_df([("a", 1.0, 0.5, "2024-01-01")])
    updated = assemble_updated_scores(kept, [])
    assert updated[ScoresCol.ID].tolist() == ["a"]


def test_assemble_with_nothing_at_all():
    assert assemble_updated_scores(empty_scores_df(), []).empty


def test_assemble_does_not_mutate_kept():
    kept = make_scores_df([("a", 1.0, 0.5, "2024-01-01")])
    assemble_updated_scores(kept, NEW_ROWS)
    assert len(kept) == 1
