import pytest
from rewrite import check_full_rewrite_inputs, item_key, rewrite_mode, stale_keys

# ── stale_keys ──────────────────────────────────────────────────────────────


def test_stale_keys_diff():
    existing = ["DATES", "ALBUM#a", "ALBUM#b", "MATCH#2024-01-01#m1"]
    new = ["DATES", "ALBUM#a", "MATCH#2024-01-01#m1"]
    assert stale_keys(existing, new) == ["ALBUM#b"]


def test_stale_keys_empty_when_no_change():
    assert stale_keys(["DATES"], ["DATES"]) == []


def test_stale_keys_tuple_keys():
    existing = [("a", "2024-01-01"), ("a", "2024-01-02"), ("b", "2024-01-01")]
    written = {("a", "2024-01-01"), ("a", "2024-01-02")}
    assert stale_keys(existing, written) == [("b", "2024-01-01")]


def test_stale_keys_empty_when_dynamodb_is_behind():
    # A key in the parquet but not yet in DynamoDB is written, never deleted.
    assert stale_keys([("m1",)], [("m1",), ("m2",)]) == []


def test_stale_keys_sorted_for_a_stable_delete_order():
    assert stale_keys(["m3", "m1", "m2"], []) == ["m1", "m2", "m3"]


def test_stale_keys_accepts_generators():
    # The handler passes generators over the scanned items.
    assert stale_keys((k for k in ["m1", "m2"]), (k for k in ["m1"])) == ["m2"]


# ── item_key ────────────────────────────────────────────────────────────────


def test_item_key_follows_key_names_order():
    item = {"date": "2024-01-01", "id": "a", "score": 1}
    assert item_key(item, ("id", "date")) == ("a", "2024-01-01")


def test_item_key_single_attribute():
    assert item_key({"match_id": "m1"}, ("match_id",)) == ("m1",)


# ── rewrite_mode ────────────────────────────────────────────────────────────


def test_rewrite_mode_incremental():
    assert rewrite_mode(False, False) is None


def test_rewrite_mode_sentinel():
    assert rewrite_mode(False, True) == "sentinel"


def test_rewrite_mode_rebuild():
    assert rewrite_mode(True, False) == "rebuild"


def test_rewrite_mode_rebuild_wins_over_sentinel():
    assert rewrite_mode(True, True) == "rebuild"


# ── check_full_rewrite_inputs ───────────────────────────────────────────────


def test_check_full_rewrite_inputs_accepts_non_empty():
    check_full_rewrite_inputs(10, 100)


def test_check_full_rewrite_inputs_rejects_empty_results():
    with pytest.raises(ValueError, match="0 results"):
        check_full_rewrite_inputs(0, 100)


def test_check_full_rewrite_inputs_rejects_empty_scores():
    with pytest.raises(ValueError, match="0 scores"):
        check_full_rewrite_inputs(10, 0)
