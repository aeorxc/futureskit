import warnings

import pytest
from futureskit.forwards import quarterly
import pandas as pd


def test_quarterly_contracts(cl):
    contracts = cl
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        res = quarterly.quarterly_contracts(contracts)
    assert res["Q2 2019"].loc[pd.to_datetime("2019-03-20")] == pytest.approx(60.18, abs=1e-2)
    assert res["Q3 2019"].loc[pd.to_datetime("2019-06-20")] == pytest.approx(56.95, abs=1e-2)
    assert res["Q4 2019"].loc[pd.to_datetime("2019-09-20")] == pytest.approx(58.01, abs=1e-2)
    assert res["Q1 2020"].loc[pd.to_datetime("2019-12-19")] == pytest.approx(61.09, abs=1e-2)
    assert res["Q2 2020"].loc[pd.to_datetime("2020-03-20")] == pytest.approx(23.14, abs=1e-2)

    res_qs = quarterly.all_quarterly_rolls(res)
    assert res_qs["Q1Q2 2020"].loc[pd.to_datetime("2019-12-19")] == pytest.approx(1.14, abs=1e-2)
    assert res_qs["Q2Q3 2019"].loc[pd.to_datetime("2019-03-20")] == pytest.approx(-0.73, abs=1e-2)
    assert res_qs["Q3Q4 2019"].loc[pd.to_datetime("2019-06-20")] == pytest.approx(0.07, abs=1e-2)
    assert res_qs["Q4Q1 2020"].loc[pd.to_datetime("2019-09-20")] == pytest.approx(0.61, abs=1e-2)

    res_qf = quarterly.all_quarterly_flys(res)
    assert res_qf["Q1Q2Q3 2020"].loc[pd.to_datetime("2019-12-19")] == pytest.approx(-0.53, abs=1e-2)
    assert res_qf["Q2Q3Q4 2019"].loc[pd.to_datetime("2019-03-20")] == pytest.approx(-0.66, abs=1e-2)
    assert res_qf["Q3Q4Q1 2019"].loc[pd.to_datetime("2019-06-20")] == pytest.approx(-0.58, abs=1e-2)
    assert res_qf["Q4Q1Q2 2020"].loc[pd.to_datetime("2019-09-20")] == pytest.approx(0.21, abs=1e-2)


def test_time_spreads_quarterly(cl):
    res = quarterly.time_spreads_quarterly(cl, m1="Q1", m2="Q2")
    assert res[2020].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.33, abs=1e-2)
    assert res[2020].loc[pd.to_datetime("2019-05-21")] == pytest.approx(1.05, abs=1e-2)

    res = quarterly.time_spreads_quarterly(cl, m1="Q4", m2="Q1")
    assert res[2020].loc[pd.to_datetime("2019-01-02")] == pytest.approx(-0.25, abs=1e-2)
    assert res[2020].loc[pd.to_datetime("2019-05-21")] == pytest.approx(0.91, abs=1e-2)


def test_fly_quarterly(cl):
    contracts = cl
    contracts = quarterly.quarterly_contracts(contracts)
    res = quarterly.fly_quarterly(contracts, x=1, y=2, z=3)
    assert res["Q1Q2Q3 2020"].loc[pd.to_datetime("2019-01-03")] == pytest.approx(-0.073, abs=1e-3)
    assert res["Q1Q2Q3 2021"].loc[pd.to_datetime("2019-05-21")] == pytest.approx(0.11, abs=1e-2)

