import numpy as np
import pandas as pd
import pytest

from futureskit import forwards
from futureskit.forwards.util import convert_contract_to_date

JAN, FEB, MAR = (pd.Timestamp(f"2026-0{m}-01") for m in (1, 2, 3))
DAYS = pd.bdate_range("2026-01-05", periods=6)


@pytest.fixture
def matrix():
    """Jan expires on day 2, Feb on day 4, Mar beyond the sample."""
    nan = np.nan
    return pd.DataFrame(
        {
            JAN: [1.0, 2.0, 3.0, nan, nan, nan],
            FEB: [10.0, 20.0, 30.0, 40.0, 50.0, nan],
            MAR: [100.0, 200.0, 300.0, 400.0, 500.0, 600.0],
        },
        index=DAYS,
    )


@pytest.fixture
def expiries():
    return {JAN: DAYS[2], FEB: DAYS[4], MAR: pd.Timestamp("2026-02-20")}


def drop_last_print(wide):
    """A deterministic stand-in for a noise detector: blank each final print."""
    out = wide.copy()
    for column in out:
        out.loc[out[column].last_valid_index(), column] = np.nan
    return out


def test_untrimmed_stitch_matches_hand_values(matrix, expiries):
    result = forwards.rolling_structure(matrix, {1: 1, 2: -1}, expiries)
    expected = [-9.0, -18.0, -27.0, -360.0, -450.0, np.nan]
    np.testing.assert_array_equal(result.to_numpy(), expected)
    assert result.name == "M1-M2"


def test_trim_blanks_each_fixed_instance_before_stitching(matrix, expiries):
    seen = {}

    def trim(wide):
        seen["wide"] = wide
        return drop_last_print(wide)

    result = forwards.rolling_structure(matrix, {1: 1, 2: -1}, expiries, trim=trim)

    wide = seen["wide"]
    assert list(wide.columns) == [(JAN, FEB), (FEB, MAR)]
    assert list(wide.columns.names) == ["M1", "M2"]
    # Each instance spans the whole frame, not only the rows it occupies.
    assert wide[(FEB, MAR)].iloc[0] == -90.0
    # Jan-Feb loses day 2 (its last print); Feb-Mar loses day 4 (its last print).
    np.testing.assert_array_equal(
        result.to_numpy(), [-9.0, -18.0, np.nan, -360.0, np.nan, np.nan]
    )


def test_fly_weights_and_label(matrix, expiries):
    result = forwards.rolling_structure(matrix, {1: 1, 2: -2, 3: 1}, expiries)
    assert result.name == "M1-2M2+M3"
    # Day 0: Jan - 2*Feb + Mar; day 3 onwards M3 is unoccupied.
    assert result.iloc[0] == 1.0 - 20.0 + 100.0
    assert result.iloc[3:].isna().all()


def test_untrimmed_equals_weighted_continuous_tenors(contracts):
    cl = contracts.rename(
        columns={x: pd.to_datetime(convert_contract_to_date(x)) for x in contracts.columns}
    )
    continuous = forwards.generate_multiple_continuous_series(cl, months=[1, 6], roll_days=2)
    result = forwards.rolling_structure(cl, {1: 1, 6: -1}, roll_days=2)
    pd.testing.assert_series_equal(
        result, (continuous["M1"] - continuous["M6"]).rename("M1-M6")
    )


@pytest.mark.parametrize("weights", [{}, {0: 1}, {1.0: 1}, {True: 1}])
def test_rejects_non_tenor_weights(matrix, expiries, weights):
    with pytest.raises(ValueError, match="positive integer tenors"):
        forwards.rolling_structure(matrix, weights, expiries)
