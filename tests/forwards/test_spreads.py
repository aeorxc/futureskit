import warnings

import pytest
from futureskit.forwards import spreads
import pandas as pd


def test_timespreads(cl):
    contracts = cl
    res = spreads.time_spreads_monthly(contracts, m1=6, m2=12)
    assert res['JunDec 2019'].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-1.51, abs=1e-2)
    assert res['JunDec 2019'].loc[pd.to_datetime("2019-05-21")] == pytest.approx(0.37, abs=1e-2)

    res = spreads.time_spreads_monthly(contracts, m1=12, m2=12)
    assert res['DecDec 2019'].loc[pd.to_datetime("2019-11-20")] == pytest.approx(3.56, abs=1e-2)
    assert res['DecDec 2020'].loc[pd.to_datetime("2019-03-20")] == pytest.approx(2.11, abs=1e-2)


def test_spread_legmap_attrs_are_nested(cl):
    expected_legs = [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-02-01")]

    spread = spreads.time_spreads_monthly(cl, m1=1, m2=2)
    assert set(spread.attrs) == {"legmap"}
    assert spread.attrs["legmap"]["JanFeb 2020"] == expected_legs

    all_spreads = spreads.all_monthly_spreads(cl)
    assert set(all_spreads.attrs) == {"legmap"}
    assert all_spreads.attrs["legmap"]["JanFeb 2020"] == expected_legs


def test_all_monthly_spreads(cl):
    res = spreads.all_monthly_spreads(cl)

    # Add your assertions here based on what you expect the output to be
    # For example:
    assert res["JanFeb 2020"].loc[pd.to_datetime("2019-01-03")] == pytest.approx(-0.10, abs=1e-2)
    assert res["JanFeb 2021"].loc[pd.to_datetime("2019-05-21")] == pytest.approx(0.31, abs=1e-2)


def test_all_monthly_spreads_extended(cl):
    from futureskit.forwards.util import convert_columns_to_date

    contracts = convert_columns_to_date(cl)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        res = spreads.all_monthly_spreads_extended(cl, col_format=None)
    assert res is not None

    dt = pd.to_datetime("2019-03-20")

    # JunJun is a 1y structure: Jun(year) - Jun(year+1)
    expected_junjun_2019 = contracts[pd.to_datetime("2019-06-01")] - contracts[pd.to_datetime("2020-06-01")]
    assert res["JunJun 2019"].loc[dt] == pytest.approx(expected_junjun_2019.loc[dt], abs=1e-8)

    # OctMar is seasonal: Oct(year) - Mar(year+1)
    expected_octmar_2019 = contracts[pd.to_datetime("2019-10-01")] - contracts[pd.to_datetime("2020-03-01")]
    assert res["OctMar 2019"].loc[dt] == pytest.approx(expected_octmar_2019.loc[dt], abs=1e-8)
