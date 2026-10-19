"""Inference over a short observation window.

A windowed frame — a handful of observation days across the whole board — is
the shape a live desk screen has, and it is where last-observation inference
used to fabricate facts. Every contract still quoted on the final row shares
that row as its last valid observation, so calling that observation an expiry
declares the entire board expired at the window's end. It is not: it only
means nothing in the sample was observed to expire.

The rule these tests pin is that only a gap proves an expiry. A column that
fell silent strictly before the last printing day expired; a column quoted
through it has an unknown expiry, is live to the last row, and never rolls
inside the sample.
"""

import numpy as np
import pandas as pd
import pytest

from futureskit.forwards import (
    BEYOND_SAMPLE,
    constant_maturity_grid,
    infer_expiry_dates,
    merge_expiry_dates,
)
from futureskit.forwards._strips import strip_mean

WINDOW = pd.bdate_range("2026-01-05", periods=8)
DELIVERIES = pd.date_range("2026-02-01", periods=40, freq="MS")


@pytest.fixture
def windowed_board():
    """Eight observation days over a forty-delivery board, all quoted throughout.

    Nothing expires inside this window; the front month's real expiry is weeks
    past its last row.
    """
    values = (
        np.arange(len(WINDOW))[:, None] * 0.01
        + np.arange(len(DELIVERIES))[None, :] * 0.5
        + 70.0
    )
    return pd.DataFrame(values, index=WINDOW, columns=DELIVERIES)


def test_a_board_quoted_through_the_window_infers_no_expiries(windowed_board):
    inferred = infer_expiry_dates(windowed_board)

    assert all(expiry == BEYOND_SAMPLE for expiry in inferred.values())
    assert not any(expiry == WINDOW[-1] for expiry in inferred.values())


def test_inference_over_a_window_still_names_exact_front_tenors(windowed_board):
    with pytest.warns(UserWarning, match="Inferring expiry dates"):
        grid = constant_maturity_grid(windowed_board, n_tenors=2, roll_days=0)

    assert (grid.contracts["M1"] == DELIVERIES[0]).all()
    assert (grid.contracts["M2"] == DELIVERIES[1]).all()


def test_an_uncurated_front_month_is_not_rolled_out_on_the_final_row(
    windowed_board,
):
    """The hazard in one assertion: no expiry evidence, so no roll."""
    with pytest.warns(UserWarning, match="Inferring expiry dates"):
        grid = constant_maturity_grid(windowed_board, n_tenors=1, roll_days=0)

    assert grid.contracts["M1"].iloc[-1] == DELIVERIES[0]
    assert grid.levels["M1"].iloc[-1] == windowed_board.iloc[-1, 0]
    assert grid.levels["M1"].notna().all()


def test_a_contract_that_fell_silent_early_still_infers_its_expiry(
    windowed_board,
):
    """A real gap is still real evidence, and still rolls the front tenor."""
    board = windowed_board.copy()
    board.iloc[4:, 0] = np.nan
    expired_on = WINDOW[3]

    assert infer_expiry_dates(board)[DELIVERIES[0]] == expired_on

    with pytest.warns(UserWarning, match="Inferring expiry dates"):
        grid = constant_maturity_grid(board, n_tenors=1, roll_days=0)

    assert grid.contracts["M1"].loc[expired_on] == DELIVERIES[0]
    assert grid.contracts["M1"].loc[WINDOW[4]] == DELIVERIES[1]


def test_a_curated_expiry_beyond_the_window_does_not_roll_inside_it(
    windowed_board,
):
    """Unknown and beyond-the-sample must reach the same selection."""
    curated = {delivery: delivery + pd.offsets.MonthEnd(0) for delivery in DELIVERIES}
    curated_grid = constant_maturity_grid(
        windowed_board, curated, n_tenors=2, roll_days=0
    )
    with pytest.warns(UserWarning, match="Inferring expiry dates"):
        inferred_grid = constant_maturity_grid(windowed_board, n_tenors=2, roll_days=0)

    pd.testing.assert_frame_equal(curated_grid.contracts, inferred_grid.contracts)
    pd.testing.assert_frame_equal(curated_grid.levels, inferred_grid.levels)


def test_a_never_observed_column_is_still_never_selected(windowed_board):
    """The load-bearing rule the fix must not disturb."""
    board = windowed_board.copy()
    board.iloc[:, 0] = np.nan

    assert pd.isna(infer_expiry_dates(board)[DELIVERIES[0]])

    with pytest.warns(UserWarning, match="Inferring expiry dates"):
        grid = constant_maturity_grid(board, n_tenors=1, roll_days=0)

    assert (grid.contracts["M1"] == DELIVERIES[1]).all()


def test_the_observed_live_board_shape(windowed_board):
    """The shape a real screen fetch has, and what it used to infer.

    OIL_BRENT_DATED over an eight-day window: 139 deliveries, curated expiries
    reaching only to Dec-2028, and the whole board quoted throughout. On 1.0.0
    the 106 uncurated deliveries from Jan-2029 to Oct-2037 each inferred the
    window's last row as their expiry. None of them may now.
    """
    window = pd.bdate_range("2026-03-23", periods=8)
    deliveries = pd.date_range("2026-04-01", periods=139, freq="MS")
    curated_through = pd.Timestamp("2028-12-01")
    board = pd.DataFrame(
        np.arange(len(window))[:, None] * 0.01
        + np.arange(len(deliveries))[None, :] * 0.1
        + 70.0,
        index=window,
        columns=deliveries,
    )
    curated = {
        delivery: delivery + pd.offsets.MonthEnd(0)
        for delivery in deliveries
        if delivery <= curated_through
    }
    uncurated = [delivery for delivery in deliveries if delivery > curated_through]
    assert (len(curated), len(uncurated)) == (33, 106)
    assert (uncurated[0], uncurated[-1]) == (
        pd.Timestamp("2029-01-01"),
        pd.Timestamp("2037-10-01"),
    )

    schedule = merge_expiry_dates(board, curated)

    assert not any(schedule[delivery] == window[-1] for delivery in deliveries)
    assert all(schedule[delivery] == BEYOND_SAMPLE for delivery in uncurated)
    assert all(schedule[delivery] == curated[delivery] for delivery in curated)

    # And the schedule is a complete, valid argument, not a partial map.
    grid = constant_maturity_grid(board, schedule, n_tenors=2, roll_days=0)
    assert (grid.contracts["M1"] == deliveries[0]).all()


def test_a_merged_schedule_round_trips_as_an_expiry_argument(windowed_board):
    """``merge_expiry_dates`` output is documented as directly re-usable."""
    schedule = merge_expiry_dates(
        windowed_board, {DELIVERIES[0]: pd.Timestamp("2026-01-20")}
    )
    grid = constant_maturity_grid(windowed_board, schedule, n_tenors=1, roll_days=0)

    assert (grid.contracts["M1"] == DELIVERIES[0]).all()


def test_a_strip_over_a_window_averages_its_live_legs(windowed_board):
    """The same hazard on the strip side: live legs must not read as expired."""
    legs = windowed_board[list(DELIVERIES[:12])]
    strip = strip_mean(legs)

    pd.testing.assert_series_equal(strip, legs.mean(axis=1), check_names=False)


def test_the_sentinel_validates_as_an_ordinary_expiry(windowed_board):
    """It is a Timestamp, so nothing in the schema layer needs to know it."""
    from futureskit.forwards import validate_expiry_dates

    schedule = infer_expiry_dates(windowed_board)

    assert validate_expiry_dates(schedule, windowed_board) == []


def test_a_never_observed_column_still_cannot_round_trip(windowed_board):
    """NaT keeps meaning "never observed", and a map is still not a guess.

    Unchanged from 1.0.0, and pinned because the sentinel exists precisely so
    that a live contract never lands in this case.
    """
    board = windowed_board.copy()
    board.iloc[:, 0] = np.nan
    schedule = infer_expiry_dates(board)

    assert pd.isna(schedule[DELIVERIES[0]])
    with pytest.raises(ValueError, match="Timestamp-like"):
        constant_maturity_grid(board, schedule, n_tenors=1, roll_days=0)
