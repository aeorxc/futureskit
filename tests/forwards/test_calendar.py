import warnings

import pandas as pd
import pytest
from futureskit.forwards import calendar
from futureskit.forwards.util import convert_columns_to_date


def test_calendar(cl):
    res = calendar.cal_contracts(cl)
    assert res is not None
    # January 2020 has expired by this date, so CAL 2020 is the balance of the
    # year over its eleven live months rather than a twelve-month strip.
    assert res["CAL 2020"]["2020-01-02"] == pytest.approx(59.174, abs=1e-3)
    # Every month is still live a year earlier, so the same strip is strict.
    assert res["CAL 2020"]["2019-01-02"] == pytest.approx(50.3325, abs=1e-3)


def test_calendar_spread(cl):
    res = calendar.cal_spreads(calendar.cal_contracts(cl))
    assert res["CAL 2020-2021"]["2020-01-02"] == pytest.approx(4.35, abs=1e-2)

def test_half_year(cl):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        res = calendar.half_year_contracts(cl)
    assert res["H1 2020"]["2019-01-02"] == pytest.approx(50.04, abs=1e-2)


def _summer_2022_columns():
    return [pd.Timestamp(2022, month, 1) for month in range(4, 10)]


def test_half_year_includes_last_complete_summer(cl):
    """Every row on which all six months quote is their plain average."""
    strip = calendar.half_year_contracts(cl)["Summer 2022"]
    contracts = convert_columns_to_date(cl)
    all_six = contracts[_summer_2022_columns()].dropna(how="any").mean(axis=1)

    pd.testing.assert_series_equal(strip.loc[all_six.index], all_six, check_names=False)


def test_half_year_prints_from_the_first_month_that_lists(cl):
    """A month that has not listed yet is not a missing quote.

    The six summer months list one by one, so requiring all six from the first
    quote would cost the strip its whole birth — 757 of its 1776 observations
    on this fixture.
    """
    summer_columns = _summer_2022_columns()
    strip = calendar.half_year_contracts(cl)["Summer 2022"].dropna()
    contracts = convert_columns_to_date(cl)
    all_six = contracts[summer_columns].dropna(how="any").mean(axis=1)

    birth = strip.index.difference(all_six.index)
    assert len(birth) > 0
    first = birth.min()
    listed = [
        column
        for column in summer_columns
        if contracts[column].first_valid_index() is not None
        and contracts[column].first_valid_index() <= first
    ]
    assert 0 < len(listed) < len(summer_columns)
    assert strip.loc[first] == pytest.approx(contracts.loc[first, listed].mean())


def test_half_year_spread(cl):
    res = calendar.half_year_spreads(calendar.half_year_contracts(cl))
    assert res["H1H2 2020"]["2019-01-02"] == pytest.approx(-0.578, abs=1e-2)
