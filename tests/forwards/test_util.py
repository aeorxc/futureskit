import numpy as np
import pytest
from futureskit import forwards
from futureskit.forwards import util
import pandas as pd


def test_convert_columns_to_date():
    df = pd.DataFrame([], columns=["2020J", "2020M", "Test"])
    res = util.convert_columns_to_date(df)
    assert pd.to_datetime("2020-04-1") in res.columns


def test_convert_contract_to_date():
    res = util.convert_contract_to_date("2020F")
    assert res == "2020-1-1"


@pytest.mark.parametrize(
    ("expiry", "roll_days", "expected"),
    [
        ("2026-01-10", 0, "2026-01-09"),  # Saturday anchors to Friday.
        ("2026-01-10", 1, "2026-01-08"),
        ("2026-01-10", 2, "2026-01-07"),
        ("2026-01-01", 0, "2026-01-01"),  # Already expired before sample.
        ("2026-01-01", 1, "2026-01-01"),
        ("2026-01-01", 2, "2026-01-01"),
        # Insufficient history means the roll is before the first observation.
        ("2026-01-10", 3, "2026-01-06 23:59:59.999999999"),
        ("2026-01-10", 4, "2026-01-06 23:59:59.999999999"),
    ],
)
def test_determine_roll_date_anchors_on_or_before_expiry(expiry, roll_days, expected):
    dates = pd.to_datetime(["2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12"])
    frame = pd.DataFrame({"price": [1.0, 2.0, 3.0, 4.0]}, index=dates)

    actual = util.determine_roll_date(frame, pd.Timestamp(expiry), roll_days)

    assert actual == pd.Timestamp(expected)


def test_extract_expiry_date_is_gone():
    """Its silent month-end fallback fabricated an expiry for any unmapped
    contract, which is the trap that made downstream code guard every call.
    """
    assert not hasattr(util, "extract_expiry_date")


def test_extract_expiry_dates_from_contracts_warns_and_delegates():
    """The deprecated name is an alias, so there is one inference rule.

    Its own rule read the last observation with no gap guard, so this column —
    quoted through the sample — used to get the sample's end date as an expiry.
    """
    index = pd.to_datetime(["2026-01-05", "2026-01-06"])
    frame = pd.DataFrame({"a": [1.0, 2.0]}, index=index)

    with pytest.warns(DeprecationWarning, match="infer_expiry_dates"):
        result = util.extract_expiry_dates_from_contracts(frame)

    assert result == {"a": forwards.BEYOND_SAMPLE}


def test_extract_expiry_dates_from_contracts_no_longer_drops_contracts():
    """Deduplication used to delete the far-tenor tail of a shared expiry."""
    index = pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07"])
    frame = pd.DataFrame(
        {"a": [1.0, np.nan, np.nan], "b": [1.0, np.nan, np.nan], "c": [1.0, 2.0, 3.0]},
        index=index,
    )

    with pytest.warns(DeprecationWarning, match="infer_expiry_dates"):
        result = util.extract_expiry_dates_from_contracts(frame)

    assert list(result) == ["a", "b", "c"]
    assert result["a"] == result["b"] == pd.Timestamp("2026-01-05")


def test_determine_roll_date_steps_back_over_business_days_before_future_expiry():
    """A future expiry still honours ``roll_days``; the sample tail is unused.

    Sunday 1-Feb anchors to Friday 30-Jan, and two business days back is
    Wednesday 28-Jan, all of it beyond the sample.
    """
    dates = pd.to_datetime(["2026-01-07", "2026-01-08", "2026-01-09"])
    frame = pd.DataFrame({"price": [1.0, 2.0, 3.0]}, index=dates)

    actual = util.determine_roll_date(frame, pd.Timestamp("2026-02-01"), 2)

    assert actual == pd.Timestamp("2026-01-28")


@pytest.mark.parametrize("roll_days", [0, 1, 2, 5, 8, 30])
@pytest.mark.parametrize(
    "sample_end", ["2026-09-03", "2026-09-04", "2026-09-07", "2026-09-08", "2026-09-09"]
)
def test_determine_roll_date_does_not_depend_on_where_the_sample_ends_on_a_weekday_calendar(
    roll_days, sample_end
):
    """A sample ending before expiry rolls where the full sample does.

    The front expires Thursday 10-Sep. The full sample prints every weekday,
    which is the calendar the extension past the truncated sample assumes, so
    the roll date is the same either way and no history is restated once the
    expiry is observed. A missing weekday breaks this; see the holiday test.
    """
    full_index = pd.bdate_range("2026-08-03", "2026-09-30")
    full = pd.DataFrame({"price": 1.0}, index=full_index)
    truncated = full.loc[:sample_end]
    expiry = pd.Timestamp("2026-09-10")

    expected = util.determine_roll_date(full, expiry, roll_days)
    actual = util.determine_roll_date(truncated, expiry, roll_days)

    assert actual == expected


def test_determine_roll_date_counts_intraday_prints_on_the_expiry_day():
    """Days are compared as dates in and beyond the sample.

    Prints are stamped 16:00 and the expiry midnight. The 10-Sep print is on
    the expiry day, so it is eligible in the full sample just as the
    extension counts 10-Sep for the truncated one; both roll on 8-Sep.
    """
    full_index = pd.bdate_range("2026-09-01", "2026-09-11") + pd.Timedelta(hours=16)
    full = pd.DataFrame({"price": 1.0}, index=full_index)
    truncated = full.loc[:"2026-09-08 16:00"]
    expiry = pd.Timestamp("2026-09-10")

    expected = util.determine_roll_date(full, expiry, 2)
    actual = util.determine_roll_date(truncated, expiry, 2)

    assert expected == pd.Timestamp("2026-09-08 16:00")
    assert actual == expected


def test_determine_roll_date_projects_late_across_a_missing_weekday():
    """Known limitation: the extension assumes every weekday prints.

    9-Sep is missing from the full sample, as a holiday would be. The truncated
    sample still counts it, so its projected roll is 8-Sep, one day later than
    the 7-Sep the full sample yields once the expiry is observed.
    """
    full_index = pd.bdate_range("2026-09-01", "2026-09-11").drop(
        pd.Timestamp("2026-09-09")
    )
    full = pd.DataFrame({"price": 1.0}, index=full_index)
    truncated = full.loc[:"2026-09-08"]
    expiry = pd.Timestamp("2026-09-10")

    assert util.determine_roll_date(full, expiry, 2) == pd.Timestamp("2026-09-07")
    assert util.determine_roll_date(truncated, expiry, 2) == pd.Timestamp("2026-09-08")


@pytest.mark.parametrize("roll_days", [0, 250, 45389, 10**6])
def test_determine_roll_date_never_rolls_beyond_sample(roll_days):
    dates = pd.to_datetime(["2026-01-07", "2026-01-08", "2026-01-09"])
    frame = pd.DataFrame({"price": [1.0, 2.0, 3.0]}, index=dates)

    actual = util.determine_roll_date(frame, forwards.BEYOND_SAMPLE, roll_days)

    assert actual == forwards.BEYOND_SAMPLE
