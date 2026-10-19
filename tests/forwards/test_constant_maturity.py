import numpy as np
import pandas as pd
import pytest

from futureskit.forwards import ConstantMaturityGrid, constant_maturity_grid


@pytest.fixture
def contract_matrix():
    deliveries = pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"])
    dates = pd.to_datetime(["2025-12-17", "2025-12-18", "2025-12-19", "2025-12-22"])
    frame = pd.DataFrame(
        [
            [70.0, 72.0, 74.0],
            [71.0, 73.0, 75.0],
            [72.0, 75.0, 77.0],
            [73.0, 77.0, 80.0],
        ],
        index=dates,
        columns=deliveries,
    )
    frame.index.name = "date"
    frame.columns.name = "delivery_month"
    return frame


@pytest.fixture
def expiry_dates(contract_matrix):
    return {
        contract_matrix.columns[0]: pd.Timestamp("2025-12-19"),
        contract_matrix.columns[1]: pd.Timestamp("2026-01-20"),
        contract_matrix.columns[2]: pd.Timestamp("2026-02-20"),
    }


def test_expiry_is_inclusive_and_changes_follow_the_assigned_contract(
    contract_matrix, expiry_dates
):
    result = constant_maturity_grid(contract_matrix, expiry_dates, n_tenors=2)

    assert isinstance(result, ConstantMaturityGrid)
    assert result.levels.at[pd.Timestamp("2025-12-19"), "M1"] == 72.0
    assert result.contracts.at[pd.Timestamp("2025-12-19"), "M1"] == pd.Timestamp(
        "2026-01-01"
    )
    assert result.changes.at[pd.Timestamp("2025-12-19"), "M1"] == 1.0

    # The next observation has rolled to Feb, whose own move is 2.0 rather
    # than the 77.0 - 72.0 gap between two delivery contracts.
    assert result.levels.at[pd.Timestamp("2025-12-22"), "M1"] == 77.0
    assert result.contracts.at[pd.Timestamp("2025-12-22"), "M1"] == pd.Timestamp(
        "2026-02-01"
    )
    assert result.changes.at[pd.Timestamp("2025-12-22"), "M1"] == 2.0
    assert result.levels.columns.tolist() == ["M1", "M2"]
    assert result.levels.columns.name == "tenor"
    pd.testing.assert_index_equal(result.levels.index, result.changes.index)
    pd.testing.assert_index_equal(result.levels.index, result.contracts.index)


def test_missing_quote_does_not_promote_a_later_contract(contract_matrix, expiry_dates):
    baseline = constant_maturity_grid(contract_matrix, expiry_dates, n_tenors=3)
    missing = contract_matrix.copy()
    missing.iloc[-1, 1] = np.nan

    result = constant_maturity_grid(missing, expiry_dates, n_tenors=3)

    assert pd.isna(result.levels.iloc[-1, 0])
    assert pd.isna(result.changes.iloc[-1, 0])
    assert result.contracts.iloc[-1, 0] == contract_matrix.columns[1]
    pd.testing.assert_frame_equal(
        result.levels.drop(columns="M1"), baseline.levels.drop(columns="M1")
    )
    pd.testing.assert_frame_equal(
        result.changes.drop(columns="M1"), baseline.changes.drop(columns="M1")
    )
    pd.testing.assert_frame_equal(result.contracts, baseline.contracts)


def test_appending_an_observation_does_not_change_prior_rows(
    contract_matrix, expiry_dates
):
    baseline = constant_maturity_grid(contract_matrix, expiry_dates, n_tenors=3)
    appended = pd.concat(
        [
            contract_matrix,
            pd.DataFrame(
                [[74.0, 78.0, 82.0]],
                index=pd.to_datetime(["2025-12-23"]),
                columns=contract_matrix.columns,
            ),
        ]
    )
    appended.index.name = contract_matrix.index.name
    appended.columns.name = contract_matrix.columns.name

    result = constant_maturity_grid(appended, expiry_dates, n_tenors=3)

    pd.testing.assert_frame_equal(result.levels.iloc[:-1], baseline.levels)
    pd.testing.assert_frame_equal(result.changes.iloc[:-1], baseline.changes)
    pd.testing.assert_frame_equal(result.contracts.iloc[:-1], baseline.contracts)


def test_inference_warns_and_preserves_contracts_sharing_expiry():
    deliveries = pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"])
    dates = pd.to_datetime(["2025-12-18", "2025-12-19"])
    matrix = pd.DataFrame(
        [[70.0, 71.0, 72.0], [np.nan, 72.0, 73.0]],
        index=dates,
        columns=deliveries,
    )

    with pytest.warns(UserWarning, match="frozen post-expiry prints"):
        result = constant_maturity_grid(matrix, n_tenors=3)

    # Feb and Mar share the inferred sample-end expiry; neither is discarded.
    assert result.contracts.loc[dates[-1]].tolist() == [
        deliveries[1],
        deliveries[2],
        pd.NaT,
    ]


def test_inference_never_selects_a_never_observed_delivery():
    """Under inference an all-NaN delivery is never live in EITHER API.

    The data is the only evidence a contract exists; a never-observed delivery
    must not occupy a tenor slot (the explicit-map path asserts existence and
    keeps the slot instead — covered elsewhere).
    """
    from futureskit.forwards.continuous import generate_series

    deliveries = pd.to_datetime(["2025-12-01", "2026-01-01", "2026-02-01"])
    dates = pd.date_range("2025-11-19", periods=3, freq="B")
    matrix = pd.DataFrame(
        {
            deliveries[0]: [10.0, 11.0, 12.0],
            deliveries[1]: [np.nan, np.nan, np.nan],
            deliveries[2]: [30.0, 31.0, 32.0],
        },
        index=dates,
        columns=deliveries,
    )

    with pytest.warns(UserWarning):
        grid = constant_maturity_grid(matrix, n_tenors=3)

    # Feb takes M2; the never-observed Jan occupies nothing.
    assert grid.levels["M2"].tolist() == [30.0, 31.0, 32.0]
    assert grid.contracts["M2"].eq(deliveries[2]).all()
    assert not grid.contracts.isin([deliveries[1]]).any().any()

    series_m2 = generate_series(matrix, front_month=2)["M2"]
    assert series_m2.tolist() == [30.0, 31.0, 32.0]


def test_roll_days_uses_determine_roll_date_trading_day_convention(
    contract_matrix, expiry_dates
):
    result = constant_maturity_grid(
        contract_matrix, expiry_dates, n_tenors=2, roll_days=1
    )

    # Jan expiry is Fri 19th, so one trading day early is Thu 18th. It remains
    # M1 on the roll date and Feb becomes M1 on Fri, matching generate_series.
    assert result.contracts.at[pd.Timestamp("2025-12-18"), "M1"] == pd.Timestamp(
        "2026-01-01"
    )
    assert result.contracts.at[pd.Timestamp("2025-12-19"), "M1"] == pd.Timestamp(
        "2026-02-01"
    )


def test_missing_expiry_mapping_is_rejected(contract_matrix, expiry_dates):
    del expiry_dates[contract_matrix.columns[-1]]

    with pytest.raises(ValueError, match="missing columns:.*2026-03"):
        constant_maturity_grid(contract_matrix, expiry_dates)


@pytest.mark.parametrize(
    ("keyword", "value", "message"),
    [
        ("n_tenors", 0, "positive integer"),
        ("n_tenors", True, "positive integer"),
        ("roll_days", -1, "non-negative integer"),
        ("roll_days", 1.5, "non-negative integer"),
    ],
)
def test_grid_parameter_validation(
    contract_matrix, expiry_dates, keyword, value, message
):
    kwargs = {keyword: value}
    with pytest.raises(ValueError, match=message):
        constant_maturity_grid(contract_matrix, expiry_dates, **kwargs)


def test_a_delivery_that_lists_later_keeps_its_tenor_slot_and_prices_nan():
    """Tenor identity is delivery order, so listing later does not vacate a slot.

    The strip builders exclude an unlisted leg from the average because a strip
    is a number that must be right or absent. A tenor is an identity: M2 is the
    second delivery whether or not it has started trading, and dropping it here
    would promote M3 into M2 and shift the whole ladder — the divergence the
    single occupant engine exists to prevent. The unlisted row prices NaN, which
    is the correct answer to "what is M2 worth", and the slot is waiting when the
    contract lists.
    """
    deliveries = pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"])
    dates = pd.date_range("2025-11-19", periods=4, freq="B")
    matrix = pd.DataFrame(
        {
            deliveries[0]: [10.0, 11.0, 12.0, 13.0],
            deliveries[1]: [np.nan, np.nan, 21.0, 22.0],
            deliveries[2]: [30.0, 31.0, 32.0, 33.0],
        },
        index=dates,
        columns=deliveries,
    )

    with pytest.warns(UserWarning, match="Inferring expiry dates"):
        grid = constant_maturity_grid(matrix, n_tenors=3, roll_days=0)

    assert (grid.contracts["M2"] == deliveries[1]).all()
    assert (grid.contracts["M3"] == deliveries[2]).all()
    assert pd.isna(grid.levels["M2"].iloc[0])
    assert grid.levels["M2"].iloc[2] == 21.0
