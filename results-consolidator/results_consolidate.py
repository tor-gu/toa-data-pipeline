import pandas as pd
from toa.columns import RedactionsCol, ResultsCol

RESULTS_COLUMNS = [ResultsCol.MATCH_ID, ResultsCol.DATE, ResultsCol.ORDER]
REDACTIONS_COLUMNS = [RedactionsCol.ID, RedactionsCol.ARTIST, RedactionsCol.ALBUM]

# A match reduced below this many albums carries no pairwise comparison at all,
# so it is dropped rather than kept as a degenerate row.
MIN_MATCH_SIZE = 2


def empty_results_df() -> pd.DataFrame:
    """The frame to merge into when no unredacted Parquet exists yet."""
    return pd.DataFrame(columns=RESULTS_COLUMNS)


def empty_redactions_df() -> pd.DataFrame:
    """The frame to merge into when no redactions Parquet exists yet."""
    return pd.DataFrame(columns=REDACTIONS_COLUMNS)


def merge_results(existing: pd.DataFrame, new_results: list[dict]) -> pd.DataFrame:
    """Upsert `new_results` into `existing` by match_id.

    Re-uploading a match replaces its row rather than duplicating it.
    """
    new_df = pd.DataFrame(new_results)[RESULTS_COLUMNS]
    new_ids = set(new_df[ResultsCol.MATCH_ID])
    kept = existing[~existing[ResultsCol.MATCH_ID].isin(new_ids)]
    return pd.concat([kept, new_df], ignore_index=True)[RESULTS_COLUMNS]


def merge_redactions(
    existing: pd.DataFrame, new_redactions: list[dict]
) -> pd.DataFrame:
    """Upsert `new_redactions` into `existing` by album id.

    Redaction files are copies of the album's name record, so re-uploading one
    refreshes the artist/album text rather than adding a second row.
    """
    new_df = pd.DataFrame(new_redactions)[REDACTIONS_COLUMNS]
    new_ids = set(new_df[RedactionsCol.ID])
    kept = existing[~existing[RedactionsCol.ID].isin(new_ids)]
    return pd.concat([kept, new_df], ignore_index=True)[REDACTIONS_COLUMNS]


def apply_redactions(unredacted: pd.DataFrame, redacted_ids: set[str]) -> pd.DataFrame:
    """Strip redacted albums out of every match ranking.

    A match keeps the comparisons among its surviving albums, so redacting one
    album out of five leaves a four-album match. Matches left with fewer than
    MIN_MATCH_SIZE albums are dropped entirely.
    """
    if not redacted_ids:
        return unredacted[RESULTS_COLUMNS].reset_index(drop=True)

    # `order` comes back from Parquet as a numpy array; the comprehension both
    # filters it and normalizes it back to the list downstream steps index into.
    trimmed = unredacted.copy()
    trimmed[ResultsCol.ORDER] = trimmed[ResultsCol.ORDER].apply(
        lambda order: [album_id for album_id in order if album_id not in redacted_ids]
    )
    kept = trimmed[trimmed[ResultsCol.ORDER].apply(len) >= MIN_MATCH_SIZE]
    return kept[RESULTS_COLUMNS].reset_index(drop=True)


def count_redacted_occurrences(unredacted: pd.DataFrame, redacted_ids: set[str]) -> int:
    """How many album slots `redacted_ids` strip out of the results."""
    if not redacted_ids or unredacted.empty:
        return 0

    per_match = unredacted[ResultsCol.ORDER].apply(
        lambda order: sum(1 for album_id in order if album_id in redacted_ids)
    )
    return int(per_match.sum())


def earliest_redacted_date(
    unredacted: pd.DataFrame, redacted_ids: set[str]
) -> str | None:
    """The earliest date on which any of `redacted_ids` appeared in a match."""
    if not redacted_ids or unredacted.empty:
        return None

    hits = unredacted[
        unredacted[ResultsCol.ORDER].apply(
            lambda order: any(album_id in redacted_ids for album_id in order)
        )
    ]
    if hits.empty:
        return None
    return min(hits[ResultsCol.DATE])


def combine_earliest(*dates: str | None) -> str | None:
    """The earliest of the given ISO dates, ignoring None. None if all are None."""
    present = [date for date in dates if date is not None]
    return min(present) if present else None
