import pytest
from initialize import InvalidInputError, normalize, unknown_fields

# ── defaults ───────────────────────────────────────────────────────────────────


def test_normalize_empty_event_takes_both_defaults():
    assert normalize({}) == {"rebuild": False, "num_executors": 1}


def test_normalize_none_event_takes_both_defaults():
    assert normalize(None) == {"rebuild": False, "num_executors": 1}


def test_normalize_results_watcher_input():
    # what results-watcher actually sends
    assert normalize({"rebuild": False}) == {"rebuild": False, "num_executors": 1}


def test_normalize_rebuild_only_fills_num_executors():
    assert normalize({"rebuild": True}) == {"rebuild": True, "num_executors": 1}


def test_normalize_num_executors_only_fills_rebuild():
    assert normalize({"num_executors": 4}) == {"rebuild": False, "num_executors": 4}


def test_normalize_both_present_is_a_passthrough():
    event = {"rebuild": True, "num_executors": 4}
    assert normalize(event) == event


# ── rebuild validation ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("rebuild", ["true", "false", "", 1, 0, None, [], {}])
def test_normalize_rejects_non_boolean_rebuild(rebuild):
    with pytest.raises(InvalidInputError, match="rebuild must be a boolean"):
        normalize({"rebuild": rebuild})


# ── num_executors validation ───────────────────────────────────────────────────


@pytest.mark.parametrize("num_executors", ["4", "", 1.5, 1.0, None, [], {}])
def test_normalize_rejects_non_integer_num_executors(num_executors):
    with pytest.raises(InvalidInputError, match="num_executors must be an integer"):
        normalize({"num_executors": num_executors})


@pytest.mark.parametrize("num_executors", [True, False])
def test_normalize_rejects_boolean_num_executors(num_executors):
    # bool is a subclass of int, so this needs its own guard
    with pytest.raises(InvalidInputError, match="num_executors must be an integer"):
        normalize({"num_executors": num_executors})


@pytest.mark.parametrize("num_executors", [0, -1, -100])
def test_normalize_rejects_num_executors_below_one(num_executors):
    with pytest.raises(InvalidInputError, match="num_executors must be at least 1"):
        normalize({"num_executors": num_executors})


def test_normalize_accepts_num_executors_of_one():
    assert normalize({"num_executors": 1})["num_executors"] == 1


# ── non-object input ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("event", ["rebuild", ["rebuild"], 42, 1.5])
def test_normalize_rejects_non_object_event(event):
    with pytest.raises(InvalidInputError, match="execution input must be an object"):
        normalize(event)


# ── unknown fields ─────────────────────────────────────────────────────────────


def test_normalize_drops_unknown_fields():
    result = normalize({"rebuild": True, "earliest_date": "2024-01-01"})
    assert result == {"rebuild": True, "num_executors": 1}


def test_unknown_fields_lists_extras_sorted():
    event = {"rebuild": True, "zebra": 1, "earliest_date": "2024-01-01"}
    assert unknown_fields(event) == ["earliest_date", "zebra"]


def test_unknown_fields_empty_when_only_known_fields():
    assert unknown_fields({"rebuild": True, "num_executors": 2}) == []


@pytest.mark.parametrize("event", [None, {}, "rebuild", 42])
def test_unknown_fields_handles_non_dict_input(event):
    assert unknown_fields(event) == []
