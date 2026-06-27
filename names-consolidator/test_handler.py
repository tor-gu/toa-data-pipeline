import pytest

from short_name import generate_short_name

MIN = 10
MAX = 20


@pytest.mark.parametrize(
    "album, expected",
    [
        # Shorter than max — returned unchanged
        ("Disintegration", "Disintegration"),
        # Shorter than min — still fits within max, returned unchanged
        ("Wish", "Wish"),
        # Word boundary found within [min, max]
        ("Everybody Else Is Doing It So Why Can't We?", "Everybody Else Is"),
        # Word boundary exactly at min (prefix length 10)
        ("Abcdefghij Klmnopqrstuvwxyz", "Abcdefghij"),
        # Word boundary exactly at max (prefix length 20)
        ("Abcdefghijklmnopqrst Xyz", "Abcdefghijklmnopqrst"),
        # No word boundary anywhere — hard truncate to max
        ("A" * 30, "A" * MAX),
        # First space is beyond max — hard truncate
        ("Abcdefghijklmnopqrstuvwxyz abc", "Abcdefghijklmnopqrst"),
        # Only space is before min — no boundary in range, hard truncate
        ("Hello Abcdefghijklmnopqrstuvwxyz", "Hello Abcdefghijklmn"),
    ],
)
def test_generate_short_name(album, expected):
    assert generate_short_name(album, MIN, MAX) == expected


@pytest.mark.parametrize(
    "album, expected",
    [
        ("21", "21"),
        ("Hotter Than July", "Hotter Than July"),
        ("Minstrel in the Gallery", "Minstrel in the"),
        ("Double Nickels on the Dime", "Double Nickels on"),
        ("Our Most Beloved", "Our Most Beloved"),
        ("Unchained", "Unchained"),
        ("Golden Lies", "Golden Lies"),
        ("The Payback", "The Payback"),
        ("Eastern Sounds", "Eastern Sounds"),
        ("Going For The One", "Going For The One"),
        ("WhipSmart", "WhipSmart"),
        ("Cutting Their Own Groove", "Cutting Their Own"),
        ("Talking Book", "Talking Book"),
        ("Permanent Waves", "Permanent Waves"),
        ("Mirror Ball", "Mirror Ball"),
        ("Countdown To Ecstasy", "Countdown To Ecstasy"),
        ("The Low Spark Of High Heeled Boys", "The Low Spark Of"),
        ("The Unforgettable Fire", "The Unforgettable"),
        ("Featuring Peggy Lee", "Featuring Peggy Lee"),
        ("Pretenders", "Pretenders"),
    ],
)
def test_generate_short_name_real_albums(album, expected):
    assert generate_short_name(album, MIN, MAX) == expected
