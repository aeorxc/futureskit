from dataclasses import FrozenInstanceError
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

import futureskit.forwards.continuous as continuous_module
from futureskit.forwards import (
    Adjustment,
    ExpiryOffset,
    RollSpec,
    constant_maturity_grid,
    generate_multiple_continuous_series,
    generate_series,
)


def _assert_pandas_timestamp_free(value):
    assert not isinstance(value, pd.Timestamp)
    if isinstance(value, (tuple, frozenset)):
        for item in value:
            _assert_pandas_timestamp_free(item)


@pytest.fixture
def roll_matrix():
    dates = pd.to_datetime(["2025-12-17", "2025-12-18", "2025-12-19", "2025-12-22"])
    deliveries = pd.to_datetime(
        ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]
    )
    matrix = pd.DataFrame(
        [
            [10.0, 20.0, 30.0, 40.0],
            [11.0, 21.0, 31.0, 41.0],
            [12.0, 22.0, 32.0, 42.0],
            [13.0, 23.0, 33.0, 43.0],
        ],
        index=dates,
        columns=deliveries,
    )
    expiries = dict(
        zip(
            deliveries,
            pd.to_datetime(["2025-12-19", "2026-01-20", "2026-02-20", "2026-03-20"]),
        )
    )
    return matrix, expiries


def test_rollspec_is_frozen_hashable_and_normalizes_data_only_values():
    anchors = {
        pd.Timestamp("2026-01-01"): pd.Timestamp("2025-12-18"),
        pd.Timestamp("2026-02-01"): pd.Timestamp("2026-01-19"),
    }
    spec = RollSpec(month_filter=[12, 6, 12], anchor_expiries=anchors)

    assert spec.month_filter == (6, 12)
    assert isinstance(next(iter(spec.anchor_expiries)), datetime)
    assert isinstance(next(iter(spec.anchor_expiries.values())), datetime)
    assert type(next(iter(spec.anchor_expiries))) is datetime
    assert type(next(iter(spec.anchor_expiries.values()))) is datetime
    equivalent = RollSpec(
        month_filter=(6, 12),
        anchor_expiries=dict(reversed(list(anchors.items()))),
    )
    assert spec == equivalent
    assert hash(spec) == hash(equivalent)
    with pytest.raises(FrozenInstanceError):
        spec.depth = 2


def test_rollspec_defaults_are_the_unadjusted_front_contract():
    spec = RollSpec()

    assert spec.depth == 1
    assert spec.month_filter is None
    assert spec.roll_rule == ExpiryOffset(days=0, lookahead_days=0)
    assert spec.adjustment is Adjustment.NONE
    assert spec.interpolate_days == 0
    assert spec.anchor_expiries is None


def test_timezone_aware_timestamp_anchor_identity_is_preserved_pandas_free():
    dates = pd.to_datetime(["2025-12-17", "2025-12-18", "2025-12-19"])
    identities = [
        pd.Timestamp("2026-01-01", tz="Europe/London"),
        pd.Timestamp("2026-02-01", tz="Europe/London"),
    ]
    matrix = pd.DataFrame(
        [[10.0, 20.0], [11.0, 21.0], [12.0, 22.0]],
        index=dates,
        columns=pd.Index(identities, dtype=object),
    )
    spec = RollSpec(
        anchor_expiries={
            identities[0]: pd.Timestamp("2025-12-18"),
            identities[1]: pd.Timestamp("2026-01-20"),
        }
    )

    stored_identities = list(spec.anchor_expiries)
    assert all(type(identity) is datetime for identity in stored_identities)
    assert all(identity.tzinfo is not None for identity in stored_identities)
    for identity in stored_identities:
        _assert_pandas_timestamp_free(identity)

    series = generate_series(matrix, roll_spec=spec)
    grid = constant_maturity_grid(matrix, n_tenors=2, roll_spec=spec)
    assert series.at[dates[-1], "M1"] == 22.0
    pd.testing.assert_series_equal(series["M1"], grid.levels["M1"])


def test_composite_anchor_identity_normalizes_nested_timestamp_and_resolves():
    dates = pd.to_datetime(["2025-12-17", "2025-12-18", "2025-12-19"])
    timestamps = [
        pd.Timestamp("2026-01-01", tz="UTC"),
        pd.Timestamp("2026-02-01", tz="UTC"),
    ]
    identities = [("leg", timestamps[0]), ("leg", timestamps[1])]
    matrix = pd.DataFrame(
        [[10.0, 20.0], [11.0, 21.0], [12.0, 22.0]],
        index=dates,
        columns=pd.Index(identities, tupleize_cols=False),
    )
    spec = RollSpec(
        anchor_expiries={
            identities[0]: pd.Timestamp("2025-12-18"),
            identities[1]: pd.Timestamp("2026-01-20"),
        }
    )

    stored_identities = list(spec.anchor_expiries)
    assert all(type(identity) is tuple for identity in stored_identities)
    assert all(type(identity[1]) is datetime for identity in stored_identities)
    for identity in stored_identities:
        _assert_pandas_timestamp_free(identity)

    series = generate_series(matrix, roll_spec=spec)
    grid = constant_maturity_grid(matrix, n_tenors=2, roll_spec=spec)
    assert series.at[dates[-1], "M1"] == 22.0
    pd.testing.assert_series_equal(series["M1"], grid.levels["M1"])


def test_frozenset_anchor_identity_is_normalized_recursively():
    identity = frozenset({"leg", pd.Timestamp("2026-01-01", tz="UTC")})
    spec = RollSpec(anchor_expiries={identity: pd.Timestamp("2025-12-18")})

    stored_identity = next(iter(spec.anchor_expiries))
    assert type(stored_identity) is frozenset
    _assert_pandas_timestamp_free(stored_identity)
    assert spec.anchor_expiries[identity].isoformat() == "2025-12-18T00:00:00"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"depth": 0},
        {"depth": True},
        {"month_filter": []},
        {"month_filter": [0]},
        {"month_filter": [True]},
        {"roll_rule": "expiry"},
        {"adjustment": "none"},
        {"interpolate_days": -1},
        {"interpolate_days": 2},
        {"adjustment": Adjustment.INTERPOLATED},
        {"anchor_expiries": {"x": "2026-01-01"}},
        {"anchor_expiries": {"x": pd.Timestamp("2026-01-01", tz="Europe/London")}},
    ],
)
def test_rollspec_rejects_invalid_combinations(kwargs):
    with pytest.raises((TypeError, ValueError)):
        RollSpec(**kwargs)


def test_expiry_offset_rejects_negative_days_and_future_lookahead():
    with pytest.raises(ValueError, match="non-negative"):
        ExpiryOffset(days=-1)
    with pytest.raises(ValueError, match="future observations"):
        ExpiryOffset(lookahead_days=1)


def test_legacy_roll_days_matches_preferred_rollspec(roll_matrix):
    matrix, expiries = roll_matrix
    rule = RollSpec(roll_rule=ExpiryOffset(days=1))

    legacy = generate_series(matrix, expiries, roll_days=1)
    preferred = generate_series(matrix, expiries, roll_spec=rule)
    pd.testing.assert_frame_equal(preferred, legacy)

    legacy_grid = constant_maturity_grid(matrix, expiries, n_tenors=3, roll_days=1)
    preferred_grid = constant_maturity_grid(
        matrix, expiries, n_tenors=3, roll_spec=rule
    )
    for preferred_frame, legacy_frame in zip(preferred_grid, legacy_grid):
        pd.testing.assert_frame_equal(preferred_frame, legacy_frame)


def test_depth_and_month_filter_share_the_canonical_occupancy_engine():
    dates = pd.to_datetime(["2026-11-19", "2026-11-20", "2026-11-23"])
    deliveries = pd.to_datetime(
        ["2026-06-01", "2026-12-01", "2027-06-01", "2027-12-01", "2028-12-01"]
    )
    matrix = pd.DataFrame(
        [[10, 20, 30, 40, 50], [11, 21, 31, 41, 51], [12, 22, 32, 42, 52]],
        index=dates,
        columns=deliveries,
        dtype=float,
    )
    expiries = dict(
        zip(
            deliveries,
            pd.to_datetime(
                ["2026-05-20", "2026-11-20", "2027-05-20", "2027-11-20", "2028-11-20"]
            ),
        )
    )
    spec = RollSpec(depth=2, month_filter=(12,))

    series = generate_series(matrix, expiries, roll_spec=spec)
    grid = constant_maturity_grid(matrix, expiries, n_tenors=2, roll_spec=spec)

    assert series.columns.tolist() == ["M2"]
    assert grid.levels.columns.tolist() == ["M2", "M3"]
    pd.testing.assert_series_equal(series["M2"], grid.levels["M2"])
    assert grid.contracts["M2"].tolist() == [
        deliveries[3],
        deliveries[3],
        deliveries[4],
    ]
    assert grid.contracts["M3"].tolist()[:2] == [deliveries[4], deliveries[4]]
    assert pd.isna(grid.contracts["M3"].iloc[-1])


def test_month_filter_rejects_opaque_columns_at_the_selection_boundary():
    matrix = pd.DataFrame(
        {"prompt": [1.0], "next": [2.0]},
        index=pd.to_datetime(["2026-01-01"]),
    )
    expiries = {
        "prompt": pd.Timestamp("2026-01-20"),
        "next": pd.Timestamp("2026-02-20"),
    }

    with pytest.raises(ValueError, match="date-like forward column identities"):
        generate_series(matrix, expiries, roll_spec=RollSpec(month_filter=1))


def test_anchor_expiries_control_roll_timing_without_pandas_in_spec(roll_matrix):
    matrix, expiries = roll_matrix
    anchors = dict(expiries)
    anchors[matrix.columns[0]] = pd.Timestamp("2025-12-18")
    spec = RollSpec(anchor_expiries=anchors)

    anchored = generate_series(matrix, roll_spec=spec)
    anchored_grid = constant_maturity_grid(matrix, n_tenors=2, roll_spec=spec)
    native = generate_series(matrix, expiries)

    assert anchored.at[pd.Timestamp("2025-12-19"), "M1"] == 22.0
    pd.testing.assert_series_equal(anchored["M1"], anchored_grid.levels["M1"])
    assert native.at[pd.Timestamp("2025-12-19"), "M1"] == 12.0


def test_backward_spread_adjustment_maps_existing_back_adjust_math(roll_matrix):
    matrix, expiries = roll_matrix
    legacy = generate_series(matrix, expiries, back_adjust=True)
    preferred = generate_series(
        matrix,
        expiries,
        roll_spec=RollSpec(adjustment=Adjustment.BACKWARD_SPREAD),
    )
    pd.testing.assert_frame_equal(preferred, legacy)


@pytest.mark.parametrize(
    ("adjustment", "interpolate_days", "expected"),
    [
        (Adjustment.BACKWARD_SPREAD, 0, [20.0, 21.0, 22.0, 23.0]),
        (Adjustment.FORWARD_SPREAD, 0, [10.0, 11.0, 12.0, 13.0]),
        (
            Adjustment.BACKWARD_RATIO,
            0,
            [10.0 * 22.0 / 12.0, 11.0 * 22.0 / 12.0, 22.0, 23.0],
        ),
        (
            Adjustment.FORWARD_RATIO,
            0,
            [10.0, 11.0, 12.0, 23.0 * 12.0 / 22.0],
        ),
        (Adjustment.PERPETUAL, 3, [40.0 / 3.0, 53.0 / 3.0, 22.0, 23.0]),
        (Adjustment.INTERPOLATED, 3, [40.0 / 3.0, 53.0 / 3.0, 22.0, 23.0]),
    ],
)
def test_adjustment_modes_match_hand_computed_examples(
    roll_matrix, adjustment, interpolate_days, expected
):
    matrix, expiries = roll_matrix
    spec = RollSpec(
        adjustment=adjustment,
        interpolate_days=interpolate_days,
    )

    result = generate_series(matrix, expiries, roll_spec=spec)

    np.testing.assert_allclose(result["M1"], expected)


@pytest.mark.parametrize("adjustment", [Adjustment.PERPETUAL, Adjustment.INTERPOLATED])
def test_truncated_blend_normalizes_over_available_window(roll_matrix, adjustment):
    matrix, expiries = roll_matrix
    spec = RollSpec(adjustment=adjustment, interpolate_days=10)

    result = generate_series(matrix, expiries, roll_spec=spec)

    # Only three outgoing rows are available, so incoming weights are 1/3, 2/3, 1:
    # 10*2/3 + 20*1/3 = 40/3; 11*1/3 + 21*2/3 = 53/3; 12*0 + 22*1 = 22.
    expected = [40.0 / 3.0, 53.0 / 3.0, 22.0, 23.0]
    np.testing.assert_allclose(result["M1"], expected)


def test_forward_spread_accumulates_each_occupied_roll():
    dates = pd.to_datetime(
        ["2025-12-17", "2025-12-18", "2025-12-19", "2025-12-22", "2025-12-23"]
    )
    deliveries = pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"])
    matrix = pd.DataFrame(
        [
            [10.0, 20.0, 40.0],
            [11.0, 21.0, 41.0],
            [12.0, 22.0, 42.0],
            [13.0, 23.0, 43.0],
            [14.0, 24.0, 44.0],
        ],
        index=dates,
        columns=deliveries,
    )
    expiries = dict(zip(deliveries, pd.to_datetime([dates[1], dates[3], "2026-02-20"])))

    result = generate_series(
        matrix,
        expiries,
        roll_spec=RollSpec(adjustment=Adjustment.FORWARD_SPREAD),
    )

    np.testing.assert_allclose(result["M1"], [10.0, 11.0, 12.0, 13.0, 14.0])


def test_filtered_path_adjustment_skips_ineligible_delivery_columns():
    dates = pd.to_datetime(["2025-12-17", "2025-12-18", "2025-12-19", "2025-12-22"])
    deliveries = pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"])
    matrix = pd.DataFrame(
        [
            [10.0, 100.0, 30.0],
            [11.0, 101.0, 31.0],
            [12.0, 102.0, 32.0],
            [13.0, 103.0, 33.0],
        ],
        index=dates,
        columns=deliveries,
    )
    expiries = dict(
        zip(deliveries, pd.to_datetime([dates[2], "2026-01-20", "2026-02-20"]))
    )
    spec = RollSpec(
        month_filter=(1, 3),
        adjustment=Adjustment.FORWARD_SPREAD,
    )

    result = generate_series(matrix, expiries, roll_spec=spec)

    np.testing.assert_allclose(result["M1"], [10.0, 11.0, 12.0, 13.0])
    assert [row[0] for row in result.attrs["mask_switch"]] == [0, 0, 0, 2]


@pytest.mark.parametrize(
    "adjustment",
    [
        Adjustment.BACKWARD_SPREAD,
        Adjustment.FORWARD_SPREAD,
        Adjustment.BACKWARD_RATIO,
        Adjustment.FORWARD_RATIO,
    ],
)
@pytest.mark.parametrize("missing_column", [0, 1])
def test_missing_roll_price_is_a_neutral_axis_adjustment(
    roll_matrix, adjustment, missing_column
):
    matrix, expiries = roll_matrix
    matrix.iloc[2, missing_column] = np.nan
    raw = generate_series(matrix, expiries, roll_spec=RollSpec())

    adjusted = generate_series(
        matrix,
        expiries,
        roll_spec=RollSpec(adjustment=adjustment),
    )

    np.testing.assert_allclose(adjusted["M1"], raw["M1"], equal_nan=True)


@pytest.mark.parametrize(
    ("adjustment", "column", "role"),
    [
        (Adjustment.BACKWARD_RATIO, 0, "outgoing"),
        (Adjustment.BACKWARD_RATIO, 1, "incoming"),
        (Adjustment.FORWARD_RATIO, 0, "outgoing"),
        (Adjustment.FORWARD_RATIO, 1, "incoming"),
    ],
)
def test_zero_roll_price_rejects_ratio_adjustment(
    roll_matrix, adjustment, column, role
):
    matrix, expiries = roll_matrix
    matrix.iloc[2, column] = 0.0

    with pytest.raises(
        ValueError,
        match=rf"2025-12-19.*{role} contract .*non-positive price 0\.0",
    ):
        generate_series(
            matrix,
            expiries,
            roll_spec=RollSpec(adjustment=adjustment),
        )


@pytest.mark.parametrize(
    ("adjustment", "column", "role"),
    [
        (Adjustment.BACKWARD_RATIO, 0, "outgoing"),
        (Adjustment.FORWARD_RATIO, 1, "incoming"),
    ],
)
def test_negative_roll_price_rejects_ratio_adjustment(
    roll_matrix, adjustment, column, role
):
    matrix, expiries = roll_matrix
    matrix.iloc[2, column] = -12.5

    with pytest.raises(
        ValueError,
        match=rf"2025-12-19.*{role} contract .*non-positive price -12\.5",
    ):
        generate_series(
            matrix,
            expiries,
            roll_spec=RollSpec(adjustment=adjustment),
        )


@pytest.mark.parametrize(
    "adjustment",
    [
        Adjustment.FORWARD_SPREAD,
        Adjustment.BACKWARD_RATIO,
        Adjustment.FORWARD_RATIO,
        Adjustment.PERPETUAL,
        Adjustment.INTERPOLATED,
    ],
)
def test_new_adjustments_reject_depth_greater_than_one(roll_matrix, adjustment):
    matrix, expiries = roll_matrix
    interpolate_days = (
        2 if adjustment in {Adjustment.PERPETUAL, Adjustment.INTERPOLATED} else 0
    )
    spec = RollSpec(
        depth=2,
        adjustment=adjustment,
        interpolate_days=interpolate_days,
    )

    with pytest.raises(
        NotImplementedError,
        match=rf"depth>1 adjustment is not yet supported.*{adjustment.value}",
    ):
        generate_series(matrix, expiries, roll_spec=spec)


def test_none_skips_roll_adjustment_work(roll_matrix, monkeypatch):
    matrix, expiries = roll_matrix

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Adjustment.NONE must not derive occupied rolls")

    monkeypatch.setattr(continuous_module, "_occupied_rolls", fail_if_called)

    result = generate_series(matrix, expiries)

    np.testing.assert_array_equal(result["M1"], [10.0, 11.0, 12.0, 23.0])


@pytest.mark.parametrize(
    ("adjustment", "interpolate_days"),
    [
        (Adjustment.BACKWARD_SPREAD, 0),
        (Adjustment.FORWARD_SPREAD, 0),
        (Adjustment.BACKWARD_RATIO, 0),
        (Adjustment.FORWARD_RATIO, 0),
        (Adjustment.PERPETUAL, 2),
        (Adjustment.INTERPOLATED, 2),
    ],
)
def test_all_adjustments_use_the_inclusive_roll_days_convention(
    roll_matrix, adjustment, interpolate_days
):
    matrix, expiries = roll_matrix
    spec = RollSpec(
        roll_rule=ExpiryOffset(days=1),
        adjustment=adjustment,
        interpolate_days=interpolate_days,
    )

    result = generate_series(matrix, expiries, roll_spec=spec)

    assert [row[0] for row in result.attrs["mask_switch"]] == [0, 0, 1, 1]
    if adjustment in {Adjustment.PERPETUAL, Adjustment.INTERPOLATED}:
        # incoming weights 0.5 then 1.0 across the two-observation blend window
        np.testing.assert_allclose(result["M1"], [15.0, 21.0, 22.0, 23.0])


def test_grid_rejects_adjustments_it_does_not_implement(roll_matrix):
    matrix, expiries = roll_matrix
    spec = RollSpec(adjustment=Adjustment.BACKWARD_SPREAD)

    with pytest.raises(NotImplementedError, match="Adjustment.NONE"):
        constant_maturity_grid(matrix, expiries, roll_spec=spec)


def test_legacy_and_rollspec_parameters_cannot_be_mixed(roll_matrix):
    matrix, expiries = roll_matrix
    spec = RollSpec()

    with pytest.raises(ValueError, match="mutually exclusive"):
        constant_maturity_grid(matrix, expiries, roll_days=0, roll_spec=spec)
    with pytest.raises(ValueError, match="front_month or back_adjust"):
        generate_series(matrix, expiries, front_month=1, roll_spec=spec)
    with pytest.raises(ValueError, match="anchor_expiries and expiry_dates"):
        generate_series(
            matrix,
            expiries,
            roll_spec=RollSpec(anchor_expiries=expiries),
        )
    with pytest.raises(ValueError, match="months"):
        generate_multiple_continuous_series(matrix, months=[1], roll_spec=spec)


def test_multiple_series_accepts_preferred_rollspec(roll_matrix):
    matrix, expiries = roll_matrix
    spec = RollSpec(depth=2, anchor_expiries=expiries)

    result = generate_multiple_continuous_series(matrix, roll_spec=spec)

    assert result.columns.tolist() == ["M2"]
