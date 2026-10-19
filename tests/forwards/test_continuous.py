import numpy as np
import pandas as pd
import pytest

from futureskit.forwards.util import convert_contract_to_date
from futureskit.forwards.continuous import generate_series


def test_generate_series_does_not_mutate_input_columns():
    contracts = pd.DataFrame(
        {
            "2020-01-01": [50.0, 51.0],
            "2020-02-01": [51.0, 52.0],
        },
        index=pd.to_datetime(["2019-12-30", "2019-12-31"]),
    )
    original = contracts.copy()

    generate_series(contracts)

    pd.testing.assert_frame_equal(contracts, original)


def test_continuous_futures(contracts):
    cl = contracts.rename(
        columns={
            x: pd.to_datetime(convert_contract_to_date(x)) for x in contracts.columns
        }
    )

    expiry_dates = {
        "2019-01-01": "2018-12-19",
        "2019-02-01": "2019-01-22",
        "2019-03-01": "2019-02-20",
        "2019-04-01": "2019-03-20",
        "2019-05-01": "2019-04-22",
        "2019-06-01": "2019-05-21",
        "2019-07-01": "2019-06-20",
        "2019-08-01": "2019-07-22",
        "2019-09-01": "2019-08-20",
        "2019-10-01": "2019-09-20",
        "2019-11-01": "2019-10-22",
        "2019-12-01": "2019-11-20",
        "2020-01-01": "2019-12-19",
        "2020-02-01": "2020-01-21",
        "2020-03-01": "2020-02-20",
        "2020-04-01": "2020-03-20",
        "2020-05-01": "2020-04-21",
        "2020-06-01": "2020-05-19",
        "2020-07-01": "2020-06-22",
        "2020-08-01": "2020-07-21",
        "2020-09-01": "2020-08-20",
        "2020-10-01": "2020-09-22",
        "2020-11-01": "2020-10-20",
        "2020-12-01": "2020-11-20",
        "2021-01-01": "2021-01-20",
        "2021-02-01": "2021-02-22",
    }
    expiry_dates = {
        pd.Timestamp(identity): pd.Timestamp(expiry)
        for identity, expiry in expiry_dates.items()
    }
    cl = cl.loc[:, cl.columns.isin(expiry_dates)]

    res = generate_series(cl, expiry_dates=expiry_dates, front_month=[1, 2])
    assert res["M1"].loc[pd.to_datetime("2020-11-20")] == pytest.approx(42.15, abs=0.01)
    assert res["M1"].loc[pd.to_datetime("2020-11-23")] == pytest.approx(43.06, abs=0.01)
    assert res["M2"].loc[pd.to_datetime("2020-11-19")] == pytest.approx(41.90, abs=0.01)
    assert res["M2"].loc[pd.to_datetime("2020-11-20")] == pytest.approx(42.42, abs=0.01)
    assert res["M2"].loc[pd.to_datetime("2020-11-23")] == pytest.approx(43.28, abs=0.01)

    res = generate_series(cl, expiry_dates=expiry_dates, roll_days=1)
    assert res["M1"].loc[pd.to_datetime("2020-11-19")] == pytest.approx(41.74, abs=0.01)
    assert res["M1"].loc[pd.to_datetime("2020-11-20")] == pytest.approx(42.42, abs=0.01)
    assert res["M1"].loc[pd.to_datetime("2020-11-23")] == pytest.approx(43.06, abs=0.01)

    res = generate_series(cl, expiry_dates=expiry_dates, front_month=2, roll_days=1)
    assert res["M2"].loc[pd.to_datetime("2020-11-19")] == pytest.approx(41.90, abs=0.01)
    assert res["M2"].loc[pd.to_datetime("2020-11-20")] == pytest.approx(42.64, abs=0.01)
    assert res["M2"].loc[pd.to_datetime("2020-11-23")] == pytest.approx(43.28, abs=0.01)

    res = generate_series(
        cl, expiry_dates=expiry_dates, front_month=1, back_adjust=True
    )
    assert res["M1"].loc[pd.to_datetime("2020-11-19")] == pytest.approx(42.01, abs=0.01)
    assert res["M1"].loc[pd.to_datetime("2020-11-20")] == pytest.approx(42.42, abs=0.01)
    assert res["M1"].loc[pd.to_datetime("2020-11-23")] == pytest.approx(43.06, abs=0.01)


def _non_parallel_curve():
    """Eight observations of four deliveries with unequal adjacent gaps.

    Adjacent deliveries are 10 apart at the front and 3 apart behind it, so a
    tenor adjusted with the front month's roll gap is visibly wrong.
    """
    dates = pd.bdate_range("2026-01-05", periods=8)
    deliveries = pd.to_datetime(
        ["2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01"]
    )
    front = [100.0 + step for step in range(8)]
    columns = [front]
    for gap in (10.0, 3.0, 3.0):
        columns.append([price + gap for price in columns[-1]])
    matrix = pd.DataFrame(dict(zip(deliveries, columns)), index=dates)
    expiries = dict(
        zip(
            deliveries,
            [
                dates[4],
                pd.Timestamp("2026-02-20"),
                pd.Timestamp("2026-03-20"),
                pd.Timestamp("2026-04-20"),
            ],
        )
    )
    return matrix, expiries


def test_back_adjust_uses_the_selected_tenor_own_roll_gap():
    matrix, expiries = _non_parallel_curve()

    raw = generate_series(matrix, expiries, front_month=2)
    adjusted = generate_series(matrix, expiries, front_month=2, back_adjust=True)

    # Raw M2 steps 114 -> 118 across the roll: the +1 daily drift plus the
    # M2/M3 gap of 3. Adjusting with M2's own gap removes the step; adjusting
    # with the front month's gap of 10 used to leave a -6 one.
    np.testing.assert_allclose(raw["M2"], [110, 111, 112, 113, 114, 118, 119, 120])
    np.testing.assert_allclose(adjusted["M2"], [113, 114, 115, 116, 117, 118, 119, 120])
    assert adjusted["M2"].diff().dropna().eq(1.0).all()


def test_back_adjust_of_several_tenors_adjusts_each_on_its_own_path():
    matrix, expiries = _non_parallel_curve()

    adjusted = generate_series(matrix, expiries, front_month=[1, 2], back_adjust=True)
    separately = [
        generate_series(matrix, expiries, front_month=month, back_adjust=True)
        for month in (1, 2)
    ]

    np.testing.assert_allclose(adjusted["M1"], separately[0]["M1"])
    np.testing.assert_allclose(adjusted["M2"], separately[1]["M2"])


def test_generate_series_results_can_be_concatenated():
    matrix, expiries = _non_parallel_curve()

    first = generate_series(matrix, expiries, front_month=1)
    second = generate_series(matrix, expiries, front_month=2)

    joined = pd.concat([first, second], axis=1)
    repeated = pd.concat([first, first], axis=1)

    assert list(joined.columns) == ["M1", "M2"]
    assert list(repeated.columns) == ["M1", "M1"]
    assert not isinstance(first.attrs["mask_switch"], np.ndarray)


def test_an_all_nan_row_is_not_a_printing_day_when_counting_back_roll_days():
    """A shut exchange must not consume one of the ``roll_days``.

    The board is blank on 2024-01-03. Counting two printing days back from the
    2024-01-05 anchor therefore reaches 2024-01-02, not 2024-01-01, so the
    outgoing February is live through 2024-01-02 and March takes the front from
    the next row on.
    """
    index = pd.to_datetime(
        [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
            "2024-01-08",
        ]
    )
    february = pd.Timestamp("2024-02-01")
    march = pd.Timestamp("2024-03-01")
    contracts = pd.DataFrame(
        [
            [10.0, 20.0],
            [11.0, 21.0],
            [np.nan, np.nan],
            [13.0, 23.0],
            [14.0, 24.0],
            [15.0, 25.0],
        ],
        index=index,
        columns=[february, march],
    )
    expiries = {february: pd.Timestamp("2024-01-05"), march: pd.Timestamp("2024-02-05")}

    result = generate_series(contracts, expiry_dates=expiries, roll_days=2)

    front = [row[0] for row in result.attrs["mask_switch"]]
    assert front == [0, 0, 1, 1, 1, 1]
    # The blank row still carries no price, but March already owns the tenor.
    assert result["M1"].tolist()[:2] == [10.0, 11.0]
    assert pd.isna(result["M1"].iloc[2])
    assert result["M1"].tolist()[3:] == [23.0, 24.0, 25.0]


def test_a_delivery_expiring_after_the_sample_does_not_roll_inside_it():
    """The front of the curve must not blank at the end of the sample.

    Both expiries fall months beyond the last observation, so no roll date
    lands inside the window and the first delivery holds M1 throughout.
    """
    index = pd.date_range("2024-01-01", periods=6, freq="B")
    february = pd.Timestamp("2024-02-01")
    march = pd.Timestamp("2024-03-01")
    contracts = pd.DataFrame(
        np.arange(12, dtype=float).reshape(6, 2), index=index, columns=[february, march]
    )
    expiries = {february: pd.Timestamp("2024-06-30"), march: pd.Timestamp("2024-07-31")}

    result = generate_series(contracts, expiry_dates=expiries, roll_days=2)

    front = [row[0] for row in result.attrs["mask_switch"]]
    assert front == [0] * len(index)
    assert result["M1"].tolist() == [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
    assert result["M1"].notna().all()
