import numpy as np
import pandas as pd
import pytest

from futureskit.forwards import constant_maturity_grid
from futureskit.forwards.continuous import generate_series


@pytest.mark.parametrize("roll_days", [0, 1, 2])
@pytest.mark.parametrize(
    "case",
    ["contiguous", "missing_month", "all_nan", "duplicate_expiry", "coverage"],
)
def test_grid_levels_equal_generate_series_for_every_tenor(case, roll_days):
    dates = pd.to_datetime(
        ["2025-12-17", "2025-12-18", "2025-12-19", "2025-12-22", "2026-01-09"]
    )
    deliveries = pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"])
    if case == "missing_month":
        deliveries = deliveries[[0, 2]]
    values = np.arange(len(dates) * len(deliveries), dtype=float).reshape(
        len(dates), len(deliveries)
    )
    matrix = pd.DataFrame(values, index=dates, columns=deliveries)
    expiries = dict(
        zip(deliveries, pd.to_datetime(["2025-12-19", "2026-01-20", "2026-02-20"]))
    )
    if case == "all_nan":
        matrix.iloc[:, 1] = np.nan
    if case == "duplicate_expiry":
        expiries[deliveries[1]] = expiries[deliveries[0]]
    if case == "coverage":
        expiries[deliveries[0]] = pd.Timestamp("2025-12-01")
        expiries[deliveries[-1]] = pd.Timestamp("2026-03-20")

    grid = constant_maturity_grid(matrix, expiries, n_tenors=4, roll_days=roll_days)
    continuous = generate_series(
        matrix, expiries, front_month=[1, 2, 3, 4], roll_days=roll_days
    )

    for tenor in grid.levels:
        pd.testing.assert_series_equal(grid.levels[tenor], continuous[tenor])


def test_all_nan_delivery_retains_tenor_identity_in_both_apis():
    dates = pd.to_datetime(["2025-11-19", "2025-11-20"])
    deliveries = pd.to_datetime(["2025-12-01", "2026-01-01", "2026-02-01"])
    matrix = pd.DataFrame(
        [[10.0, np.nan, 30.0], [11.0, np.nan, 31.0]],
        index=dates,
        columns=deliveries,
    )
    expiries = dict(
        zip(
            deliveries,
            pd.to_datetime(["2025-12-19", "2026-01-20", "2026-02-20"]),
        )
    )

    grid = constant_maturity_grid(matrix, expiries, n_tenors=3)
    continuous = generate_series(matrix, expiries, front_month=[1, 2, 3])

    assert grid.contracts["M2"].eq(deliveries[1]).all()
    assert grid.levels["M2"].isna().all()
    assert continuous["M2"].isna().all()
    pd.testing.assert_series_equal(grid.levels["M3"], continuous["M3"])


def test_opaque_column_identities_are_preserved_across_continuous_apis():
    dates = pd.to_datetime(["2025-12-18", "2025-12-19", "2025-12-22"])
    identities = ["Z prompt assessment", "A quarterly swap", ("desk", 3)]
    matrix = pd.DataFrame(
        [[10.0, 20.0, 30.0], [11.0, 21.0, 31.0], [12.0, 22.0, 32.0]],
        index=dates,
        columns=identities,
    )
    expiries = dict(
        zip(
            identities,
            pd.to_datetime(["2025-12-19", "2026-01-20", "2026-02-20"]),
        )
    )

    grid = constant_maturity_grid(matrix, expiries, n_tenors=3)
    continuous = generate_series(matrix, expiries, front_month=[1, 2, 3])

    pd.testing.assert_frame_equal(grid.levels, continuous.rename_axis("tenor", axis=1))
    assert grid.contracts.loc[dates[0]].tolist() == identities
    assert grid.contracts.at[dates[-1], "M1"] == "A quarterly swap"
