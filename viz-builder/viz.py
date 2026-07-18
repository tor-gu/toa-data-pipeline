from datetime import date, timedelta

import pandas as pd
from toa.columns import ResultsCol, ScoresCol, VizCol

SCORE_DECIMALS = 4


def largest_component(results_df):
    """Largest connected component of the match graph, where albums are
    connected iff they appeared in the same match. Ties broken by smallest
    member id so reruns are deterministic."""
    parent = {}

    def find(album_id):
        parent.setdefault(album_id, album_id)
        root = album_id
        while parent[root] != root:
            root = parent[root]
        while parent[album_id] != root:
            parent[album_id], album_id = root, parent[album_id]
        return root

    for order in results_df[ResultsCol.ORDER]:
        for album_id in order[1:]:
            parent[find(album_id)] = find(order[0])

    components = {}
    for album_id in parent:
        components.setdefault(find(album_id), set()).add(album_id)
    if not components:
        return set()
    return max(components.values(), key=lambda c: (len(c), min(c)))


def component_matches(results_df, component):
    """Matches whose albums are in the component. Every match is a clique in
    the match graph, so checking one member is checking them all."""
    mask = results_df[ResultsCol.ORDER].apply(lambda order: order[0] in component)
    return (
        results_df.loc[mask, [ResultsCol.MATCH_ID, ResultsCol.DATE, ResultsCol.ORDER]]
        .sort_values([ResultsCol.DATE, ResultsCol.MATCH_ID])
        .reset_index(drop=True)
    )


def build_dates(scores_df, matches_df):
    """Canonical date axis: every scored date, sorted, preceded by one
    synthetic "pre-season" date (the day before the first real date) at which
    every album is pre-debut and unrated, so playback starts from an all-zero
    frame. Every component match date must be present (scores-updater scores
    every result date)."""
    dates = sorted(scores_df[ScoresCol.DATE].unique())
    missing = set(matches_df[ResultsCol.DATE]) - set(dates)
    if missing:
        raise ValueError(f"match dates missing from scores: {sorted(missing)}")
    if not dates:
        return dates
    preseason = (date.fromisoformat(dates[0]) - timedelta(days=1)).isoformat()
    return [preseason] + dates


def build_album_vectors(scores_df, component, dates, matches_df):
    """One row per component album: debut index, a score vector covering every
    date (zero-filled before the debut), and the chronological list of match
    ids the album appeared in."""
    date_index = {d: i for i, d in enumerate(dates)}
    subset = scores_df[scores_df[ScoresCol.ID].isin(component)]

    unscored = component - set(subset[ScoresCol.ID])
    if unscored:
        raise ValueError(f"component albums missing from scores: {sorted(unscored)}")

    # matches_df is sorted by (date, match_id), so each album's list comes out
    # chronologically ordered. Component matches are cliques within the
    # component, so every id in ORDER is a component album.
    match_ids_by_album = {}
    for _, m in matches_df.iterrows():
        for album_id in m[ResultsCol.ORDER]:
            match_ids_by_album.setdefault(album_id, []).append(m[ResultsCol.MATCH_ID])

    rows = []
    for album_id, group in subset.groupby(ScoresCol.ID):
        by_date = dict(zip(group[ScoresCol.DATE], group[ScoresCol.SCORE]))
        indices = sorted(date_index[d] for d in by_date)
        debut = indices[0]
        if indices != list(range(debut, len(dates))):
            raise ValueError(f"score history for {album_id} has gaps")
        scores = [0.0] * debut + [
            round(float(by_date[dates[i]]), SCORE_DECIMALS)
            for i in range(debut, len(dates))
        ]
        rows.append(
            {
                VizCol.ID: album_id,
                VizCol.DEBUT: debut,
                VizCol.SCORES: scores,
                VizCol.MATCH_IDS: match_ids_by_album.get(album_id, []),
            }
        )

    rows.sort(key=lambda row: row[VizCol.ID])
    return pd.DataFrame(
        rows, columns=[VizCol.ID, VizCol.DEBUT, VizCol.SCORES, VizCol.MATCH_IDS]
    )
