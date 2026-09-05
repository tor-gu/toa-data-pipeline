import pandas as pd
from short_name import generate_short_name
from toa.columns import NamesCol

COLUMNS = [NamesCol.ID, NamesCol.ARTIST, NamesCol.ALBUM, NamesCol.SHORT_NAME]


def empty_names_df() -> pd.DataFrame:
    """The frame to merge into when no consolidated Parquet exists yet."""
    return pd.DataFrame(columns=COLUMNS)


def fill_short_names(names: list[dict], min_len: int, max_len: int) -> list[dict]:
    """Return copies of `names` with `short-name` generated where absent.

    An empty string counts as absent, so a name file can opt back into a
    generated short name by blanking the field rather than removing it.
    """
    filled = []
    for name in names:
        name = dict(name)
        if not name.get(NamesCol.SHORT_NAME):
            name[NamesCol.SHORT_NAME] = generate_short_name(
                name[NamesCol.ALBUM], min_len, max_len
            )
        filled.append(name)
    return filled


def merge_names(existing: pd.DataFrame, new_names: list[dict]) -> pd.DataFrame:
    """Upsert `new_names` into `existing` by id.

    A re-uploaded name replaces its existing row rather than duplicating it --
    the local CLI rewrites `name_<id>.json` every time an album turns up in a
    new match, so the same id arrives here repeatedly.
    """
    new_df = pd.DataFrame(new_names)[COLUMNS]
    new_ids = set(new_df[NamesCol.ID])
    kept = existing[~existing[NamesCol.ID].isin(new_ids)]
    return pd.concat([kept, new_df], ignore_index=True)[COLUMNS]
