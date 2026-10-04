"""Reads every parquet file the writer needs from the data bucket."""

from dataclasses import dataclass

import awswrangler as wr
import pandas as pd
from toa.paths import (
    ENRICHED_SCORES_KEY,
    GLOBAL_STATISTICS_KEY,
    NAMES_CONSOLIDATED_KEY,
    RESULTS_CONSOLIDATED_KEY,
    VIZ_ALBUMS_KEY,
    VIZ_DATES_KEY,
    VIZ_MATCHES_KEY,
)
from transform import build_names


@dataclass
class Inputs:
    names: dict  # album id -> {artist, album, short-name}, from build_names
    scores: pd.DataFrame
    results: pd.DataFrame
    statistics: pd.DataFrame
    viz_dates: pd.DataFrame
    viz_albums: pd.DataFrame
    viz_matches: pd.DataFrame


def read_inputs(bucket):
    def read(key):
        return wr.s3.read_parquet(f"s3://{bucket}/{key}")

    return Inputs(
        names=build_names(read(NAMES_CONSOLIDATED_KEY)),
        scores=read(ENRICHED_SCORES_KEY),
        results=read(RESULTS_CONSOLIDATED_KEY),
        statistics=read(GLOBAL_STATISTICS_KEY),
        viz_dates=read(VIZ_DATES_KEY),
        viz_albums=read(VIZ_ALBUMS_KEY),
        viz_matches=read(VIZ_MATCHES_KEY),
    )
