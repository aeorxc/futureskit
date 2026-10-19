# test_forwards.py
import pytest

from futureskit import forwards
import pandas as pd


def test_timespreads(contracts):
    res = forwards.time_spreads(contracts, m1=6, m2=12)
    assert res[2019].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-1.51, abs=0.01)
    assert res[2019].loc[pd.to_datetime("2019-05-21")] == pytest.approx(0.37, abs=0.01)

    res = forwards.time_spreads(contracts, m1=12, m2=12)
    assert res[2019].loc[pd.to_datetime("2019-11-20")] == pytest.approx(3.56, abs=0.01)
    assert res[2020].loc[pd.to_datetime("2019-03-20")] == pytest.approx(2.11, abs=0.01)


def test_timespreads_quaterly(contracts):
    res = forwards.time_spreads(contracts, m1="Q1", m2="Q2")
    assert res[2020].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.33, abs=0.01)
    assert res[2020].loc[pd.to_datetime("2019-05-21")] == pytest.approx(1.05, abs=0.01)

    res = forwards.time_spreads(contracts, m1="Q4", m2="Q1")
    assert res[2020].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.25, abs=0.01)
    assert res[2020].loc[pd.to_datetime("2019-05-21")] == pytest.approx(0.91, abs=0.01)


def test_all_spread_combinations(contracts):
    res = forwards.all_spread_combinations(contracts)
    assert "Q1" in res
    assert "Q1Q2" in res
    assert "Calendar" in res
    assert "JanFeb" in res
    assert "JanFebMar" in res


def test_spread_combination_calendar(contracts):
    res = forwards.spread_combination(contracts, "calendar")
    assert res is not None
    # January 2020 has expired, so this is the balance of the year.
    assert res[2020].loc[pd.to_datetime("2020-01-02")] == pytest.approx(59.174, abs=0.01)


def test_spread_combination_calendar_spread(contracts):
    res = forwards.spread_combination(contracts, "calendar spread")
    assert res["CAL 2020-2021"].loc[pd.to_datetime("2020-01-02")] == pytest.approx(4.35, abs=0.01)


def test_spread_combination_half_year(contracts):
    res = forwards.spread_combination(contracts, "half year")
    assert res["H1 2020"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(50.04, abs=0.01)


def test_spread_combination_half_year_spread(contracts):
    res = forwards.spread_combination(contracts, "half year spread")
    assert res["H1H2 2020"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.578, abs=0.01)


def test_spread_combination_quarter(contracts):
    res = forwards.spread_combination(contracts, "q1")
    assert res["Q1 2020"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(49.88, abs=0.01)


def test_spread_combination_quarter_spread(contracts):
    res = forwards.spread_combination(contracts, "q1q2")
    assert res["Q1Q2 2020"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.33, abs=0.01)

    res = forwards.spread_combination(contracts, "q1q3")
    assert res["Q1Q3 2020"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.58, abs=0.01)


def test_spread_combination_monthly(contracts):
    res = forwards.spread_combination(contracts, "monthly", col_format="%b%b %y")

    assert res["JanFeb 20"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.11, abs=0.01)
    assert res["FebMar 21"].loc[pd.to_datetime("2020-01-02")] == pytest.approx(0.35, abs=0.01)


def test_spread_combination_quaterly(contracts):
    res = forwards.spread_combination(contracts, "quarterly")

    assert res["Q1 20"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(49.88, abs=0.01)
    assert res["Q2 21"].loc[pd.to_datetime("2020-01-02")] == pytest.approx(55.16, abs=0.01)


def test_spread_combination_quaterly_roll(contracts):
    res = forwards.spread_combination(contracts, "quarterly roll")

    assert res["Q1Q2 20"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.32, abs=0.01)
    assert res["Q4Q1 21"].loc[pd.to_datetime("2020-01-02")] == pytest.approx(0.61, abs=0.01)


def test_spread_combination_fly(contracts):
    res = forwards.spread_combination(contracts, "fly")

    assert res["JanFebMar 21"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(0.009, abs=0.01)
    assert res["DecJanFeb 21"].loc[pd.to_datetime("2020-01-02")] == pytest.approx(0.0199, abs=0.01)


def test_spread_combination_quaterly_fly(contracts):
    res = forwards.spread_combination(contracts, "quarterly fly")

    assert res["Q1Q2Q3 20"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.076, abs=0.01)
    assert res["Q4Q1Q2 21"].loc[pd.to_datetime("2020-01-02")] == pytest.approx(0.15, abs=0.01)


def test_spread_combination_month(contracts):
    res = forwards.spread_combination(contracts, "jan")
    assert res["Jan 2020"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(49.77, abs=0.01)


def test_spread_combination_month_spread_janfeb(contracts):
    res = forwards.spread_combination(contracts, "janfeb")
    assert res["JanFeb 2020"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.11, abs=0.01)


def test_spread_combination_month_spread_decjan(contracts):
    res = forwards.spread_combination(contracts, "decjan")
    assert res["DecJan 2020"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.06, abs=0.01)


def test_spread_combination_month_fly(contracts):
    res = forwards.spread_combination(contracts, "janfebmar")
    assert res["JanFebMar 2020"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(0.0, abs=0.01)


def test_spread_combination_quarter_fly(contracts):
    res = forwards.spread_combination(contracts, "q4q1q2")
    assert res["Q4Q1Q2 2020"].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.023, abs=0.01)


@pytest.mark.parametrize(
    ("combination_type", "column", "current_value"),
    [
        ("q1q2", "Q1Q2 2020", -0.33),
        ("janfeb", "JanFeb 2020", -0.11),
        ("q1q2q3", "Q1Q2Q3 2020", -0.076),
    ],
)
def test_exclude_price_month_masks_structure_inputs(
    contracts, combination_type, column, current_value
):
    unexcluded = forwards.spread_combination(
        contracts, combination_type, exclude_price_month=False
    )
    excluded = forwards.spread_combination(
        contracts, combination_type, exclude_price_month=True
    )

    masked_contracts = forwards.replace_last_month_with_nan(
        forwards.convert_columns_to_date(contracts)
    )
    expected = forwards.spread_combination(
        masked_contracts, combination_type, exclude_price_month=False
    )

    assert unexcluded[column].loc[pd.Timestamp("2019-01-02")] == pytest.approx(
        current_value, abs=0.01
    )
    assert not excluded.equals(unexcluded)
    pd.testing.assert_frame_equal(excluded, expected)


def test_recent_spreads(contracts):
    res = forwards.recent_spreads(contracts, combination_type="contracts")
    assert res is not None


def test_recent_structure(contracts):
    res = forwards.recent_structure(contracts)
    assert res is not None


