import pandas as pd
import pytest
from consolidate import COLUMNS, empty_names_df, fill_short_names, merge_names
from toa.columns import NamesCol

MIN = 10
MAX = 20


def name(id_, artist, album, short_name):
    return {
        NamesCol.ID: id_,
        NamesCol.ARTIST: artist,
        NamesCol.ALBUM: album,
        NamesCol.SHORT_NAME: short_name,
    }


def make_names_df(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


def ids(df):
    return list(df[NamesCol.ID])


def row_for(df, id_):
    return df[df[NamesCol.ID] == id_].iloc[0].to_dict()


# ── fill_short_names ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "supplied, expected",
    [
        # Supplied short name wins, even when the album would fit as-is
        ("Disintegr.", "Disintegr."),
        # Missing entirely — generated from the album title
        (None, "Everybody Else Is"),
        # Empty string counts as absent, so it opts back into generation
        ("", "Everybody Else Is"),
    ],
)
def test_fill_short_names_short_name_default(supplied, expected):
    uploaded = {
        NamesCol.ID: "aaaa000000000001",
        NamesCol.ARTIST: "The Cranberries",
        NamesCol.ALBUM: "Everybody Else Is Doing It So Why Can't We?",
    }
    if supplied is not None:
        uploaded[NamesCol.SHORT_NAME] = supplied

    filled = fill_short_names([uploaded], MIN, MAX)

    assert len(filled) == 1
    assert filled[0][NamesCol.SHORT_NAME] == expected


def test_fill_short_names_does_not_mutate_input():
    uploaded = {
        NamesCol.ID: "aaaa000000000001",
        NamesCol.ARTIST: "The Cure",
        NamesCol.ALBUM: "Disintegration",
    }

    fill_short_names([uploaded], MIN, MAX)

    assert NamesCol.SHORT_NAME not in uploaded


# ── merge_names ───────────────────────────────────────────────────────────────


def test_merge_into_empty_frame():
    new = [name("aaaa000000000001", "The Cure", "Disintegration", "Disintegration")]

    merged = merge_names(empty_names_df(), new)

    assert list(merged.columns) == COLUMNS
    assert ids(merged) == ["aaaa000000000001"]


def test_merge_appends_new_id():
    existing = make_names_df(
        [name("aaaa000000000001", "The Cure", "Disintegration", "Disintegration")]
    )
    new = [name("aaaa000000000002", "Wire", "Pink Flag", "Pink Flag")]

    merged = merge_names(existing, new)

    assert sorted(ids(merged)) == ["aaaa000000000001", "aaaa000000000002"]


def test_merge_upserts_existing_id():
    existing = make_names_df(
        [
            name("aaaa000000000001", "The Cure", "Disintegration", "Disintegration"),
            name("aaaa000000000002", "Wire", "Pink Flag", "Pink Flag"),
        ]
    )
    new = [name("aaaa000000000001", "The Cure", "Disintegration", "Disintegr.")]

    merged = merge_names(existing, new)

    assert len(merged) == 2
    assert ids(merged).count("aaaa000000000001") == 1
    assert row_for(merged, "aaaa000000000001")[NamesCol.SHORT_NAME] == "Disintegr."
    # The untouched row survives unchanged
    assert row_for(merged, "aaaa000000000002")[NamesCol.SHORT_NAME] == "Pink Flag"


def test_merge_projects_to_columns_in_order():
    existing = empty_names_df()
    new = [
        {
            NamesCol.SHORT_NAME: "Pink Flag",
            NamesCol.ALBUM: "Pink Flag",
            NamesCol.ID: "aaaa000000000002",
            NamesCol.ARTIST: "Wire",
        }
    ]

    merged = merge_names(existing, new)

    assert list(merged.columns) == COLUMNS
