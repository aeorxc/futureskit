"""The strip builders are functions of their arguments, not of the calendar."""

import numpy as np
import pandas as pd

from futureskit import forwards
from futureskit.forwards import calendar

DATES = pd.date_range("2019-06-03", periods=40, freq="B")


def _monthly_frame(*years, months=range(1, 13)):
    """A contract matrix with one column per delivery month of each year."""
    columns = [pd.Timestamp(year, month, 1) for year in years for month in months]
    values = np.arange(len(DATES) * len(columns), dtype=float).reshape(
        len(DATES), len(columns)
    )
    return pd.DataFrame(values, index=DATES, columns=columns)


def test_cal_inclusion_of_a_partial_year_follows_as_of_not_the_clock():
    contracts = pd.concat(
        [_monthly_frame(2020), _monthly_frame(2021, months=range(1, 6))], axis=1
    )

    within = calendar.cal_contracts(contracts, as_of=pd.Timestamp("2021-06-30"))
    outside = calendar.cal_contracts(contracts, as_of=pd.Timestamp("2020-06-30"))

    # The part-built year is carved in only when it is the as_of year.
    assert "CAL 2021" in within.columns
    assert "CAL 2021" not in outside.columns
    # The complete year is unaffected by as_of either way.
    assert "CAL 2020" in within.columns
    assert "CAL 2020" in outside.columns


def test_cal_contracts_is_a_function_of_its_arguments_alone():
    contracts = pd.concat(
        [_monthly_frame(2020), _monthly_frame(2021, months=range(1, 6))], axis=1
    )
    as_of = pd.Timestamp("2021-06-30")

    pd.testing.assert_frame_equal(
        calendar.cal_contracts(contracts, as_of=as_of),
        calendar.cal_contracts(contracts, as_of=as_of),
    )


def test_recent_spreads_window_follows_as_of():
    contracts = _monthly_frame(2020, 2021)

    early = forwards.recent_spreads(
        contracts, "contracts", as_of=pd.Timestamp("2020-03-15")
    )
    late = forwards.recent_spreads(
        contracts, "contracts", as_of=pd.Timestamp("2020-09-15")
    )

    # A minus-three to plus-six month window centred on as_of, so the two
    # windows select different deliveries.
    assert list(early.columns) == [
        "jan20",
        "feb20",
        "mar20",
        "apr20",
        "may20",
        "jun20",
        "jul20",
        "aug20",
        "sep20",
    ]
    assert list(late.columns) == [
        "jul20",
        "aug20",
        "sep20",
        "oct20",
        "nov20",
        "dec20",
        "jan21",
        "feb21",
        "mar21",
    ]


def test_recent_spreads_is_deterministic_for_one_as_of():
    contracts = _monthly_frame(2020, 2021)
    as_of = pd.Timestamp("2020-09-15")

    pd.testing.assert_frame_equal(
        forwards.recent_spreads(contracts, "contracts", as_of=as_of),
        forwards.recent_spreads(contracts, "contracts", as_of=as_of),
    )
