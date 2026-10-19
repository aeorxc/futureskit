"""A monthly delivery cannot be live after its delivery month ends.

Some venues keep publishing a terminal settlement for a contract that has
already expired — ICE cleared swaps do — so the price series has no gap at
expiry and last-observation inference reads the dead contract as alive. On a
September window that put an expired August swap in M1.

The cap is grammar, not a calendar. When a column label is anchored on a month
start — the only label shape that names a delivery month — the inferred expiry
is capped at the last calendar day of that month. Nothing here consults an
expiry table, an exchange holiday calendar or a per-root rule, a curated expiry
is never touched, and a dated label is not a monthly delivery.
"""

import numpy as np
import pandas as pd
import pytest

from futureskit.forwards import (
    BEYOND_SAMPLE,
    constant_maturity_grid,
    infer_expiry_dates,
    merge_expiry_dates,
    util,
)
from futureskit.forwards._strips import strip_mean

SEPTEMBER_WINDOW = pd.bdate_range("2026-09-01", periods=8)
DELIVERIES = pd.date_range("2026-08-01", periods=4, freq="MS")
AUGUST, SEPTEMBER, OCTOBER, NOVEMBER = DELIVERIES


def board(index=SEPTEMBER_WINDOW, columns=DELIVERIES):
    values = (
        np.arange(len(index))[:, None] * 0.01
        + np.arange(len(columns))[None, :] * 0.5
        + 70.0
    )
    return pd.DataFrame(values, index=index, columns=columns)


@pytest.fixture
def spilled_board():
    """A September window on which the expired August delivery still prints."""
    return board()


def test_a_spilled_delivery_expires_at_its_month_end(spilled_board):
    inferred = infer_expiry_dates(spilled_board)

    assert inferred[AUGUST] == pd.Timestamp("2026-08-31")


def test_a_september_observation_never_selects_an_august_delivery(spilled_board):
    with pytest.warns(UserWarning, match="Inferring expiry dates"):
        grid = constant_maturity_grid(spilled_board, n_tenors=3, roll_days=0)

    assert (grid.contracts["M1"] == SEPTEMBER).all()
    assert (grid.contracts["M2"] == OCTOBER).all()
    assert not (grid.contracts == AUGUST).any().any()


def test_a_month_still_running_stays_beyond_sample(spilled_board):
    inferred = infer_expiry_dates(spilled_board)

    assert inferred[SEPTEMBER] == BEYOND_SAMPLE
    assert inferred[OCTOBER] == BEYOND_SAMPLE
    assert inferred[NOVEMBER] == BEYOND_SAMPLE


def test_a_delivery_that_fell_silent_keeps_its_last_print():
    contracts = board()
    contracts.loc[SEPTEMBER_WINDOW[3:], NOVEMBER] = np.nan

    inferred = infer_expiry_dates(contracts)

    assert inferred[NOVEMBER] == SEPTEMBER_WINDOW[2]


def test_a_curated_expiry_is_never_capped(spilled_board):
    curated = {AUGUST: pd.Timestamp("2026-09-04")}

    schedule = merge_expiry_dates(spilled_board, curated)

    assert schedule[AUGUST] == pd.Timestamp("2026-09-04")
    assert schedule[SEPTEMBER] == BEYOND_SAMPLE


def test_a_curated_expiry_inside_the_month_is_untouched(spilled_board):
    schedule = merge_expiry_dates(spilled_board, {AUGUST: pd.Timestamp("2026-08-20")})

    assert schedule[AUGUST] == pd.Timestamp("2026-08-20")


def test_an_opaque_label_carries_no_month_to_cap():
    contracts = board(columns=["front", "second", "third", "fourth"])

    inferred = infer_expiry_dates(contracts)

    assert all(expiry == BEYOND_SAMPLE for expiry in inferred.values())


def test_a_never_observed_delivery_stays_nat(spilled_board):
    spilled_board[AUGUST] = np.nan

    assert pd.isna(infer_expiry_dates(spilled_board)[AUGUST])


def test_roll_days_steps_back_from_a_capped_expiry():
    """The capped date is a real expiry, so ``roll_days`` applies to it."""
    contracts = board(index=pd.bdate_range("2026-08-26", periods=8))

    with pytest.warns(UserWarning, match="Inferring expiry dates"):
        immediate = constant_maturity_grid(contracts, n_tenors=1, roll_days=0)
        early = constant_maturity_grid(contracts, n_tenors=1, roll_days=1)

    assert immediate.contracts["M1"].loc["2026-08-31"] == AUGUST
    assert immediate.contracts["M1"].loc["2026-09-01"] == SEPTEMBER
    assert early.contracts["M1"].loc["2026-08-28"] == AUGUST
    assert early.contracts["M1"].loc["2026-08-31"] == SEPTEMBER


def test_a_dated_label_is_not_a_monthly_delivery():
    """A prompt point or cargo date carries no delivery month to cap.

    Labels are opaque and the schema puts no calendar meaning on them, so only
    a month start names a month. Reading August out of 2026-08-15 would expire
    a Dated Brent-style assessment at a month end it never had.
    """
    dated = pd.to_datetime(["2026-08-15", "2026-08-20"])
    contracts = board(columns=dated)

    inferred = infer_expiry_dates(contracts)

    assert all(expiry == BEYOND_SAMPLE for expiry in inferred.values())


def test_a_label_carrying_a_time_is_not_a_month_anchor():
    stamped = [pd.Timestamp("2026-08-01 09:30"), pd.Timestamp("2026-09-01 09:30")]
    contracts = board(columns=stamped)

    inferred = infer_expiry_dates(contracts)

    assert all(expiry == BEYOND_SAMPLE for expiry in inferred.values())


def test_the_deprecated_extractor_inherits_the_cap(spilled_board):
    """One inference rule: the deprecated alias cannot bypass the cap.

    Its result validates as a complete expiry map, so a caller handing it back
    to a continuous-series call used to reproduce the spill-over in full.
    """
    with pytest.warns(DeprecationWarning, match="infer_expiry_dates"):
        extracted = util.extract_expiry_dates_from_contracts(spilled_board)

    assert extracted[AUGUST] == pd.Timestamp("2026-08-31")

    grid = constant_maturity_grid(spilled_board, extracted, n_tenors=1, roll_days=0)
    assert (grid.contracts["M1"] == SEPTEMBER).all()


def test_a_month_that_ends_on_the_last_printing_day_is_not_capped():
    """The guard is strict: a month running on the final row has not ended."""
    contracts = board(index=pd.bdate_range("2026-08-20", periods=8))

    assert contracts.index[-1] == pd.Timestamp("2026-08-31")
    assert infer_expiry_dates(contracts)[AUGUST] == BEYOND_SAMPLE


def test_a_month_end_that_is_not_a_printing_day_anchors_on_the_last_one():
    """May 2026 ends on a Sunday, and roll_days counts printing days from there."""
    deliveries = pd.date_range("2026-05-01", periods=2, freq="MS")
    may, june = deliveries
    contracts = board(index=pd.bdate_range("2026-05-27", periods=8), columns=deliveries)

    assert infer_expiry_dates(contracts)[may] == pd.Timestamp("2026-05-31")

    with pytest.warns(UserWarning, match="Inferring expiry dates"):
        immediate = constant_maturity_grid(contracts, n_tenors=1, roll_days=0)
        early = constant_maturity_grid(contracts, n_tenors=1, roll_days=1)

    assert immediate.contracts["M1"].loc["2026-05-29"] == may
    assert immediate.contracts["M1"].loc["2026-06-01"] == june
    assert early.contracts["M1"].loc["2026-05-28"] == may
    assert early.contracts["M1"].loc["2026-05-29"] == june


def test_a_leap_february_ends_on_the_twenty_ninth():
    deliveries = pd.date_range("2028-02-01", periods=2, freq="MS")
    contracts = board(index=pd.bdate_range("2028-03-02", periods=8), columns=deliveries)

    assert infer_expiry_dates(contracts)[deliveries[0]] == pd.Timestamp("2028-02-29")


def test_a_december_delivery_ends_at_the_year_end():
    deliveries = pd.to_datetime(["2026-12-01", "2027-01-01"])
    contracts = board(index=pd.bdate_range("2027-01-04", periods=8), columns=deliveries)

    assert infer_expiry_dates(contracts)[deliveries[0]] == pd.Timestamp("2026-12-31")


def test_a_strip_leg_inherits_the_cap(spilled_board):
    """Strip liveness reads the same map, so a dead leg leaves the strip."""
    legs = spilled_board[[AUGUST, SEPTEMBER, OCTOBER]]

    strip = strip_mean(legs)

    pd.testing.assert_series_equal(
        strip, legs[[SEPTEMBER, OCTOBER]].mean(axis=1), check_names=False
    )
