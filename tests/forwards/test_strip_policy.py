"""One partial-strip policy across the calendar, quarterly and half-year
builders, and one empty-input convention.

The policy is that a strip requires every leg live on the observation date, and
a leg is live between listing and expiry. A delivery that has not listed yet is
not missing data, it has not started; an expired delivery is not missing data,
it is over; a listed, unexpired delivery with no quote is missing data and
withholds the strip.
"""

import numpy as np
import pandas as pd
import pytest

from futureskit import forwards
from futureskit.forwards import calendar, quarterly

DATES = pd.date_range("2019-06-03", periods=40, freq="B")


def _monthly_frame(*years, months=range(1, 13)):
    """A contract matrix with one column per delivery month of each year."""
    columns = [pd.Timestamp(year, month, 1) for year in years for month in months]
    values = np.arange(len(DATES) * len(columns), dtype=float).reshape(
        len(DATES), len(columns)
    )
    return pd.DataFrame(values, index=DATES, columns=columns)


# --- min_legs: one partial-strip policy across the three builders ---------


def test_an_expired_leg_is_not_required_and_the_strip_prints_its_balance():
    contracts = _monthly_frame(2020)
    # January stops printing part way through: it has expired, not gone dark.
    expired_leg = pd.Timestamp(2020, 1, 1)
    contracts.loc[DATES[10] :, expired_leg] = np.nan
    row = DATES[20]

    strict = calendar.cal_contracts(contracts)

    remaining = [pd.Timestamp(2020, m, 1) for m in range(2, 13)]
    assert strict.loc[row, "CAL 2020"] == pytest.approx(
        contracts.loc[row, remaining].mean()
    )
    # Before it expired, all twelve were required and quoted.
    assert strict.loc[DATES[5], "CAL 2020"] == pytest.approx(
        contracts.loc[DATES[5], list(contracts.columns)].mean()
    )


def test_a_live_leg_with_no_quote_still_withholds_the_strip():
    contracts = _monthly_frame(2020)
    expired_leg = pd.Timestamp(2020, 1, 1)
    contracts.loc[DATES[10] :, expired_leg] = np.nan
    row = DATES[20]
    # A month that is still trading simply has no print on this date.
    contracts.loc[row, pd.Timestamp(2020, 7, 1)] = np.nan

    assert pd.isna(calendar.cal_contracts(contracts).loc[row, "CAL 2020"])


def test_an_unlisted_leg_is_not_required_and_the_strip_prints_its_birth():
    """The months of a far year list one by one, and the strip starts anyway.

    Requiring all twelve from the year's first quote costs a calendar every
    observation until its last month arrives — the whole of its birth.
    """
    contracts = _monthly_frame(2026)
    late_legs = [pd.Timestamp(2026, month, 1) for month in range(7, 13)]
    # The second half of the year has not listed yet on the early rows.
    contracts.loc[: DATES[10], late_legs] = np.nan
    row = DATES[5]

    listed = [pd.Timestamp(2026, month, 1) for month in range(1, 7)]
    assert calendar.cal_contracts(contracts).loc[row, "CAL 2026"] == pytest.approx(
        contracts.loc[row, listed].mean()
    )


def test_an_unlisted_leg_is_still_required_once_it_lists():
    """The birth ends at the first quote, not at some looser rule."""
    contracts = _monthly_frame(2026)
    late_leg = pd.Timestamp(2026, 7, 1)
    contracts.loc[: DATES[10], late_leg] = np.nan
    row = DATES[20]
    # Listed on DATES[11], and silent again here: that is a missing quote.
    contracts.loc[row, late_leg] = np.nan

    assert pd.isna(calendar.cal_contracts(contracts).loc[row, "CAL 2026"])


def test_a_never_listed_leg_is_never_required():
    contracts = _monthly_frame(2026)
    contracts[pd.Timestamp(2026, 7, 1)] = np.nan
    row = DATES[5]

    remaining = [pd.Timestamp(2026, month, 1) for month in range(1, 13) if month != 7]
    assert calendar.cal_contracts(contracts).loc[row, "CAL 2026"] == pytest.approx(
        contracts.loc[row, remaining].mean()
    )


def test_a_forward_year_stays_strict_on_all_twelve_legs():
    contracts = pd.concat([_monthly_frame(2020), _monthly_frame(2026)], axis=1)
    row = DATES[5]

    # Nothing in 2026 has expired within this sample, so all twelve are required.
    assert calendar.cal_contracts(contracts).loc[row, "CAL 2026"] == pytest.approx(
        contracts.loc[row, [pd.Timestamp(2026, m, 1) for m in range(1, 13)]].mean()
    )

    contracts.loc[row, pd.Timestamp(2026, 4, 1)] = np.nan
    assert pd.isna(calendar.cal_contracts(contracts).loc[row, "CAL 2026"])


def test_a_curated_expiry_map_decides_liveness_instead_of_the_data():
    contracts = _monthly_frame(2020)
    row = DATES[20]
    curated = {
        pd.Timestamp(2020, month, 1): (
            DATES[10] if month == 1 else DATES[-1] + pd.Timedelta(days=365)
        )
        for month in range(1, 13)
    }

    # January is curated as expired even though it is still printing, so it is
    # neither required nor averaged in.
    curated_result = calendar.cal_contracts(contracts, expiry_dates=curated)
    remaining = [pd.Timestamp(2020, m, 1) for m in range(2, 13)]
    assert curated_result.loc[row, "CAL 2020"] == pytest.approx(
        contracts.loc[row, remaining].mean()
    )
    # Inference alone would have kept all twelve live and averaged them.
    assert calendar.cal_contracts(contracts).loc[row, "CAL 2020"] == pytest.approx(
        contracts.loc[row, list(contracts.columns)].mean()
    )


def test_cal_requires_every_leg_by_default():
    contracts = _monthly_frame(2020)
    row = DATES[5]
    for month in (3, 7, 11):
        contracts.loc[row, pd.Timestamp(2020, month, 1)] = np.nan

    strict = calendar.cal_contracts(contracts)

    assert pd.isna(strict.loc[row, "CAL 2020"])
    # Every other row still has all twelve legs and is unaffected.
    assert strict["CAL 2020"].drop(row).notna().all()


def test_cal_min_legs_lowers_the_bar_deliberately():
    contracts = _monthly_frame(2020)
    row = DATES[5]
    present = [pd.Timestamp(2020, m, 1) for m in range(1, 13)]
    for month in (3, 7, 11):
        contracts.loc[row, pd.Timestamp(2020, month, 1)] = np.nan
        present.remove(pd.Timestamp(2020, month, 1))

    lenient = calendar.cal_contracts(contracts, min_legs=9)

    assert lenient.loc[row, "CAL 2020"] == pytest.approx(
        contracts.loc[row, present].mean()
    )
    # Ten legs are not nine, so a stricter bar still refuses the same row.
    assert pd.isna(calendar.cal_contracts(contracts, min_legs=10).loc[row, "CAL 2020"])


def test_an_expired_leg_is_excluded_for_quarters_and_halves_too():
    contracts = _monthly_frame(2020)
    contracts.loc[DATES[10] :, pd.Timestamp(2020, 1, 1)] = np.nan
    row = DATES[20]

    quarters = quarterly.quarterly_contracts(contracts)
    halves = calendar.half_year_contracts(contracts)

    assert quarters.loc[row, "Q1 2020"] == pytest.approx(
        contracts.loc[row, [pd.Timestamp(2020, m, 1) for m in (2, 3)]].mean()
    )
    assert halves.loc[row, "H1 2020"] == pytest.approx(
        contracts.loc[row, [pd.Timestamp(2020, m, 1) for m in range(2, 7)]].mean()
    )


def test_quarter_and_half_year_defaults_are_unchanged():
    contracts = _monthly_frame(2020)
    row = DATES[5]
    contracts.loc[row, pd.Timestamp(2020, 2, 1)] = np.nan

    quarters = quarterly.quarterly_contracts(contracts)
    halves = calendar.half_year_contracts(contracts)

    # One missing leg has always been enough to withhold a quarter or a half.
    assert pd.isna(quarters.loc[row, "Q1 2020"])
    assert pd.isna(halves.loc[row, "H1 2020"])
    # Strips that do not contain the missing month are untouched.
    assert quarters.loc[row, "Q2 2020"] == pytest.approx(
        contracts.loc[row, [pd.Timestamp(2020, m, 1) for m in (4, 5, 6)]].mean()
    )
    assert halves.notna().loc[row, "H2 2020"]


def test_quarter_and_half_year_accept_min_legs():
    contracts = _monthly_frame(2020)
    row = DATES[5]
    contracts.loc[row, pd.Timestamp(2020, 2, 1)] = np.nan

    quarters = quarterly.quarterly_contracts(contracts, min_legs=2)
    halves = calendar.half_year_contracts(contracts, min_legs=5)

    assert quarters.loc[row, "Q1 2020"] == pytest.approx(
        contracts.loc[row, [pd.Timestamp(2020, m, 1) for m in (1, 3)]].mean()
    )
    assert halves.loc[row, "H1 2020"] == pytest.approx(
        contracts.loc[row, [pd.Timestamp(2020, m, 1) for m in (1, 3, 4, 5, 6)]].mean()
    )


def test_min_legs_reaches_the_builders_through_spread_combination():
    contracts = _monthly_frame(2020)
    row = DATES[5]
    contracts.loc[row, pd.Timestamp(2020, 3, 1)] = np.nan

    assert pd.isna(
        forwards.spread_combination(contracts, "calendar", col_format="%Y").loc[
            row, 2020
        ]
    )
    assert forwards.spread_combination(
        contracts, "calendar", col_format="%Y", min_legs=11
    ).loc[row, 2020] == pytest.approx(
        contracts.loc[row].drop(pd.Timestamp(2020, 3, 1)).mean()
    )


# --- one empty-input convention -------------------------------------------


def test_strip_builders_return_an_empty_frame_rather_than_none_or_raising():
    # Two deliveries can form no calendar, quarter or half-year strip at all.
    contracts = _monthly_frame(2020, months=(1, 2))
    as_of = pd.Timestamp("2015-06-30")

    results = {
        "cal_contracts": calendar.cal_contracts(contracts, as_of=as_of),
        "half_year_contracts": calendar.half_year_contracts(contracts),
        "quarterly_contracts": quarterly.quarterly_contracts(contracts),
    }
    for name, res in results.items():
        assert isinstance(res, pd.DataFrame), name
        assert res.empty, name
        assert list(res.columns) == [], name
        pd.testing.assert_index_equal(res.index, contracts.index)


def test_spread_builders_return_an_empty_frame_for_an_empty_strip_frame():
    empty = calendar.cal_contracts(
        _monthly_frame(2020, months=(1, 2)), as_of=pd.Timestamp("2015-06-30")
    )

    results = {
        "cal_spreads": calendar.cal_spreads(empty),
        "half_year_spreads": calendar.half_year_spreads(empty),
        "all_quarterly_rolls": quarterly.all_quarterly_rolls(empty),
    }
    for name, res in results.items():
        assert isinstance(res, pd.DataFrame), name
        assert res.empty, name
        pd.testing.assert_index_equal(res.index, empty.index)


# --- never-observed legs must not break the datetime bounds ----------------


def test_a_strip_of_only_never_observed_legs_is_all_nan():
    contracts = _monthly_frame(2026)
    for month in (1, 2, 3):
        contracts[pd.Timestamp(2026, month, 1)] = np.nan

    q1 = quarterly.quarterly_contracts(contracts)
    assert q1["Q1 2026"].isna().all()
    # the other quarters are untouched by the empty legs
    assert q1["Q2 2026"].notna().all()


def test_a_never_observed_leg_beside_live_legs_is_simply_not_required():
    contracts = _monthly_frame(2026)
    contracts[pd.Timestamp(2026, 2, 1)] = np.nan
    row = DATES[5]

    q1 = quarterly.quarterly_contracts(contracts)
    remaining = [pd.Timestamp(2026, 1, 1), pd.Timestamp(2026, 3, 1)]
    assert q1.loc[row, "Q1 2026"] == pytest.approx(contracts.loc[row, remaining].mean())


def test_an_ary_shaped_empty_delivery_tail_does_not_raise():
    # CME_NymexFutures_EOD:ARY carries seven 2022 delivery columns with no
    # observations at all; on numpy >= 2.5 the datetime64 bound build raised
    # TypeError for every strip touching them and the quarterly panels blanked.
    contracts = _monthly_frame(2022, 2023)
    for month in range(1, 8):
        contracts[pd.Timestamp(2022, month, 1)] = np.nan

    q = quarterly.quarterly_contracts(contracts)
    assert q["Q1 2022"].isna().all()
    assert q["Q2 2022"].isna().all()
    assert q["Q3 2022"].notna().any()
    assert q["Q1 2023"].notna().all()
