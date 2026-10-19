import pandas as pd
import pytest

from futureskit import forwards
from futureskit.forwards.continuous import generate_multiple_continuous_series
from futureskit.forwards.structure import (
    forward_rolling_structure,
    generate_structure_series,
    rolling_structure,
)
from futureskit.forwards.util import convert_contract_to_date

FLY = {1: 1, 2: -2, 3: 1}


def test_continuous_futures(contracts):
    cl = contracts.rename(
        columns={
            x: pd.to_datetime(convert_contract_to_date(x))
            for x in contracts.columns
        }
    )

    res = generate_structure_series(cl, mx=1, my=2)
    assert res["M1-M2"].loc[pd.to_datetime("2020-11-20")] == pytest.approx(-0.27, abs=0.01)


@pytest.fixture
def three_deliveries():
    """Three fully observed deliveries, so inference expires them all together."""
    index = pd.to_datetime(
        ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"]
    )
    return pd.DataFrame(
        {
            "front": [10.0, 11.0, 12.0, 13.0, 14.0],
            "second": [20.0, 21.0, 22.0, 23.0, 24.0],
            "third": [25.0, 26.0, 27.0, 28.0, 29.0],
        },
        index=index,
    )


def test_structure_without_expiry_dates_never_rolls_a_fully_observed_frame(
    three_deliveries,
):
    """The inferred baseline: every column expires at the sample end."""
    res = generate_structure_series(three_deliveries, mx=1, my=2)

    assert set(res["M1-M2"]) == {-10.0}


def test_structure_honours_supplied_expiry_dates(three_deliveries):
    """A curated front-month expiry rolls M1-M2 mid-sample.

    Without the passthrough this frame cannot roll at all, which is what
    forced consumers to rebuild the M1-M2 stitch outside futureskit.
    """
    res = generate_structure_series(
        three_deliveries,
        mx=1,
        my=2,
        expiry_dates={
            "front": pd.Timestamp("2026-01-07"),
            "second": pd.Timestamp("2026-01-09"),
            "third": pd.Timestamp("2026-01-09"),
        },
    )

    spread = res["M1-M2"]
    assert spread.loc[pd.Timestamp("2026-01-07")] == -10.0
    assert spread.loc[pd.Timestamp("2026-01-08")] == -5.0


def test_structure_rolls_before_a_future_expiry_without_restating_history():
    """A sample ending before the front expiry still rolls ``roll_days`` early.

    Sep26 expires Thursday 10-Sep, so roll_days=5 keeps it live through
    Thursday 3-Sep and M1-M3 moves to Oct26-Dec26 on Friday 4-Sep. A sample
    that ends on Tuesday 8-Sep used to keep Sep26-Nov26 until the expiry
    entered the sample, then restate those days.
    """
    deliveries = pd.to_datetime(
        ["2026-09-01", "2026-10-01", "2026-11-01", "2026-12-01"]
    )
    index = pd.bdate_range("2026-08-17", "2026-09-30")
    contracts = pd.DataFrame(
        {delivery: price for delivery, price in zip(deliveries, [100.0, 90.0, 85.0, 82.0])},
        index=index,
    )
    expiries = dict(
        zip(
            deliveries,
            pd.to_datetime(["2026-09-10", "2026-10-12", "2026-11-10", "2026-12-10"]),
        )
    )

    def structure(end):
        return generate_structure_series(
            contracts.loc[:end], mx=1, my=3, roll_days=5, expiry_dates=expiries
        )["M1-M3"]

    full, truncated = structure("2026-09-30"), structure("2026-09-08")

    assert truncated.loc[:"2026-09-03"].eq(15.0).all()
    assert truncated.loc["2026-09-04":].eq(8.0).all()
    pd.testing.assert_series_equal(truncated, full.loc[truncated.index])


# --------------------------------------------------------------------------
# An irregular eight-delivery board with a weekend expiry


ROLLING_DELIVERIES = pd.date_range("2026-09-01", periods=8, freq="MS")
# 2026-10-10 is a Saturday: the forward tests need a weekend expiry.
ROLLING_EXPIRIES = dict(
    zip(
        ROLLING_DELIVERIES,
        pd.to_datetime(
            [
                "2026-08-20",
                "2026-09-21",
                "2026-10-10",
                "2026-11-19",
                "2026-12-17",
                "2027-01-20",
                "2027-02-18",
                "2027-03-18",
            ]
        ),
    )
)


@pytest.fixture
def rolling_contracts():
    """Eight deliveries over a window that rolls the front month four times.

    Levels and drifts are irregular across deliveries, so no adjacent fly is
    zero, and a leg that picks the wrong delivery or the wrong roll date
    changes the answer.
    """
    index = pd.bdate_range("2026-08-03", "2026-12-31")
    step = pd.Series(range(len(index)), index=index, dtype=float)
    levels = [80.0, 78.7, 78.1, 76.2, 75.9, 73.4, 72.8, 70.1]
    drifts = [0.11, 0.07, 0.13, 0.05, 0.09, 0.02, 0.12, 0.04]
    return pd.DataFrame(
        {
            delivery: level + step * drift
            for delivery, level, drift in zip(ROLLING_DELIVERIES, levels, drifts)
        },
        index=index,
    )


def _continuous(contracts, months, roll_days=0):
    return generate_multiple_continuous_series(
        contracts, months=months, roll_days=roll_days, expiry_dates=ROLLING_EXPIRIES
    )


@pytest.mark.parametrize("roll_days", [0, 3])
def test_rolling_fly_equals_weighted_continuous_tenors(rolling_contracts, roll_days):
    """The fly the forward builds on, on a board where flies are not zero."""
    fly = rolling_structure(rolling_contracts, FLY, ROLLING_EXPIRIES, roll_days)
    legs = _continuous(rolling_contracts, [1, 2, 3], roll_days=roll_days)

    expected = legs["M1"] - 2 * legs["M2"] + legs["M3"]
    pd.testing.assert_series_equal(fly, expected.rename("M1-2M2+M3"))
    assert fly.abs().min() > 0.1


def test_rolling_fly_moves_with_roll_days(rolling_contracts):
    unrolled = rolling_structure(rolling_contracts, FLY, ROLLING_EXPIRIES, 0)
    rolled = rolling_structure(rolling_contracts, FLY, ROLLING_EXPIRIES, 3)

    assert (rolled - unrolled).abs().max() > 0.1


def test_structures_are_exported():
    assert forwards.rolling_structure is rolling_structure
    assert forwards.forward_rolling_structure is forward_rolling_structure


# --------------------------------------------------------------------------
# generate_structure_series is a wrapper: pin it to the 1.0.5 implementation


def _structure_series_1_0_5(contracts, mx=1, my=2, roll_days=0, mx_df=None,
                            my_df=None, expiry_dates=None):
    """``generate_structure_series`` exactly as released in futureskit 1.0.5."""
    colname = f"M{mx}-M{my}"
    if mx_df is not None and my_df is not None:
        df = pd.concat([mx_df, my_df], axis=1)
    else:
        df = generate_multiple_continuous_series(contracts, months=[mx, my], roll_days=roll_days,
                                                 expiry_dates=expiry_dates)
    df[colname] = df[f"M{mx}"].sub(df[f"M{my}"]).dropna()
    df = df[[colname]]
    df = df.dropna(how="all", axis="rows")
    return df


def _assert_identical(new, old):
    """Same values, label, dtype and index, compared exactly.

    ``attrs`` are not compared: 1.0.5 leaked the continuous series'
    ``mask_switch`` onto the spread, and the rolling_structure wrapper does
    not carry it (no consumer reads it from a structure).
    """
    pd.testing.assert_frame_equal(new, old, check_exact=True, check_freq=True)


@pytest.mark.parametrize("mx,my,roll_days", [(1, 2, 0), (1, 3, 0), (2, 1, 0), (1, 6, 2)])
def test_structure_series_is_unchanged_on_the_cl_fixture(contracts, mx, my, roll_days):
    cl = contracts.rename(
        columns={x: pd.to_datetime(convert_contract_to_date(x)) for x in contracts.columns}
    )

    _assert_identical(
        generate_structure_series(cl, mx=mx, my=my, roll_days=roll_days),
        _structure_series_1_0_5(cl, mx=mx, my=my, roll_days=roll_days),
    )


@pytest.mark.parametrize("roll_days", [0, 3])
def test_structure_series_is_unchanged_with_curated_expiries(rolling_contracts, roll_days):
    _assert_identical(
        generate_structure_series(
            rolling_contracts, mx=1, my=3, roll_days=roll_days, expiry_dates=ROLLING_EXPIRIES
        ),
        _structure_series_1_0_5(
            rolling_contracts, mx=1, my=3, roll_days=roll_days, expiry_dates=ROLLING_EXPIRIES
        ),
    )


def test_structure_series_is_unchanged_from_prebuilt_legs(rolling_contracts):
    legs = _continuous(rolling_contracts, [1, 2])

    with pytest.warns(DeprecationWarning, match="removed in futureskit 2.0"):
        new = generate_structure_series(
            rolling_contracts, mx=1, my=2, mx_df=legs["M1"], my_df=legs["M2"]
        )
    old = _structure_series_1_0_5(
        rolling_contracts, mx=1, my=2, mx_df=legs["M1"], my_df=legs["M2"]
    )

    _assert_identical(new, old)
    assert new.attrs == old.attrs


def test_structure_series_rejects_a_zero_width_spread(rolling_contracts):
    """1.0.5 raised on mx == my; the dict wrapper must not quietly return -M1."""
    with pytest.raises(ValueError):
        generate_structure_series(rolling_contracts, mx=2, my=2)


@pytest.mark.parametrize("dtype", ["uint8", "uint64", "int64", "float64"])
def test_structure_series_is_unchanged_from_named_prebuilt_frames(dtype):
    """Prebuilt legs keep 1.0.5 subtraction: unsigned dtypes and axis names."""
    index = pd.to_datetime(["2026-01-05", "2026-01-06"])
    mx_df = pd.DataFrame({"M1": [70, 71]}, index=index, dtype=dtype)
    my_df = pd.DataFrame({"M2": [69, 69]}, index=index, dtype=dtype)
    mx_df.columns.name = my_df.columns.name = "tenor"

    with pytest.warns(DeprecationWarning):
        new = generate_structure_series(None, mx=1, my=2, mx_df=mx_df, my_df=my_df)
    old = _structure_series_1_0_5(None, mx=1, my=2, mx_df=mx_df, my_df=my_df)

    _assert_identical(new, old)
    assert new.attrs == old.attrs
    assert new.columns.name == "tenor"
    assert new["M1-M2"].tolist() == [1, 2]


# --------------------------------------------------------------------------
# forward_rolling_structure


def test_forward_starts_where_the_history_ends(rolling_contracts):
    """At roll_days=0 the first projected day carries the last history value.

    The history ends on Thursday 1-Oct; nothing expires before the next
    business day, so holding the last row flat cannot move the fly.
    """
    contracts = rolling_contracts.loc[:"2026-10-01"]
    history = rolling_structure(contracts, FLY, ROLLING_EXPIRIES).dropna()

    forward = forward_rolling_structure(
        contracts.iloc[-1], ROLLING_EXPIRIES, FLY, start=contracts.index[-1]
    )

    assert forward.name == history.name == "M1-2M2+M3"
    assert forward.index[0] == pd.Timestamp("2026-10-02")
    assert forward.iloc[0] == history.iloc[-1]


@pytest.mark.parametrize("roll_days", [0, 1, 3])
def test_forward_rolls_on_the_days_the_history_will(rolling_contracts, roll_days):
    """The forward is the history of a curve that never moves again.

    Observing the held-flat curve on every later business day must give the
    projection exactly, roll dates included.
    """
    start = pd.Timestamp("2026-09-28")
    curve = rolling_contracts.loc[start]
    observed = pd.DataFrame(
        [curve.to_numpy()] * len(rolling_contracts.loc[start:]),
        index=rolling_contracts.loc[start:].index,
        columns=rolling_contracts.columns,
    )
    later = rolling_structure(observed, FLY, ROLLING_EXPIRIES, roll_days)

    forward = forward_rolling_structure(
        curve, ROLLING_EXPIRIES, FLY, roll_days=roll_days, start=start,
        horizon_months=3,
    )

    pd.testing.assert_series_equal(
        forward, later.loc[forward.index], check_freq=False
    )
    assert forward.index[-1] > pd.Timestamp("2026-11-19")


@pytest.mark.parametrize(
    "roll_days,last_outgoing,first_incoming",
    [
        (0, "2026-10-09", "2026-10-12"),
        (1, "2026-10-08", "2026-10-09"),
        (3, "2026-10-06", "2026-10-07"),
    ],
)
def test_forward_fly_rolls_a_weekend_expiry_counting_back_from_friday(
    rolling_contracts, roll_days, last_outgoing, first_incoming
):
    """Nov26 expires Saturday 10-Oct, so its last trading day is Friday 9-Oct.

    The fly holds Nov-Dec-Jan through ``roll_days`` trading days before that
    Friday, then moves to Dec-Jan-Feb on the next business day. Expected
    values come straight from the curve, not through the library.
    """
    start = pd.Timestamp("2026-10-01")
    curve = rolling_contracts.loc[start]
    nov, dec, jan, feb = (curve[d] for d in ROLLING_DELIVERIES[2:6])
    outgoing, incoming = nov - 2 * dec + jan, dec - 2 * jan + feb
    assert abs(outgoing - incoming) > 0.1

    fly = forward_rolling_structure(
        curve, ROLLING_EXPIRIES, FLY, roll_days=roll_days, start=start,
        horizon_months=1,
    )

    assert fly.loc[:last_outgoing].tolist() == pytest.approx(
        [outgoing] * len(fly.loc[:last_outgoing])
    )
    assert fly.loc[first_incoming] == pytest.approx(incoming)
    assert pd.bdate_range(last_outgoing, first_incoming).size == 2


def test_forward_rejects_a_missing_expiry_schedule(rolling_contracts):
    """Inference would read the flat projection as never expiring."""
    curve = rolling_contracts.loc["2026-10-01"]

    with pytest.raises(ValueError, match="requires expiry_dates"):
        forward_rolling_structure(
            curve, None, {1: 1, 2: -1}, start=pd.Timestamp("2026-10-01")
        )


def test_forward_stops_when_a_leg_runs_off_the_curve(rolling_contracts):
    start = pd.Timestamp("2026-10-01")
    curve = rolling_contracts.loc[start].iloc[:5]
    expiries = {delivery: ROLLING_EXPIRIES[delivery] for delivery in curve.index}

    forward = forward_rolling_structure(
        curve, expiries, FLY, start=start, horizon_months=6
    )

    # Nov26, Dec26 and Jan27 are live until Nov26 expires on Saturday 10-Oct;
    # from Monday 12-Oct only two deliveries remain and the fly cannot be built.
    assert forward.index[-1] == pd.Timestamp("2026-10-09")


def test_forward_requires_an_expiry_for_every_curve_entry(rolling_contracts):
    curve = rolling_contracts.loc["2026-10-01"]
    expiries = dict(list(ROLLING_EXPIRIES.items())[:-1])

    with pytest.raises(ValueError, match="missing columns"):
        forward_rolling_structure(
            curve, expiries, {1: 1, 2: -1}, start=pd.Timestamp("2026-10-01")
        )


@pytest.mark.parametrize("gap", ["absent", "null"])
def test_forward_truncate_stops_at_the_first_delivery_without_an_expiry(
    rolling_contracts, gap
):
    """Equals projecting the curve cut by hand, as the dashboard did.

    The gap sits mid-curve with a known expiry after it: that later delivery
    must be dropped too, not slid into the gap's tenor.
    """
    start = pd.Timestamp("2026-10-01")
    curve = rolling_contracts.loc[start]
    expiries = dict(ROLLING_EXPIRIES)
    if gap == "absent":
        del expiries[ROLLING_DELIVERIES[5]]
    else:
        expiries[ROLLING_DELIVERIES[5]] = pd.NaT

    truncated = forward_rolling_structure(
        curve, expiries, FLY, start=start, horizon_months=6,
        on_missing_expiry="truncate",
    )
    manual = forward_rolling_structure(
        curve.iloc[:5], {d: ROLLING_EXPIRIES[d] for d in ROLLING_DELIVERIES[:5]},
        FLY, start=start, horizon_months=6,
    )

    pd.testing.assert_series_equal(truncated, manual, check_exact=True)
    assert not truncated.empty


def test_forward_truncate_with_no_usable_delivery_is_empty(rolling_contracts):
    start = pd.Timestamp("2026-10-01")
    curve = rolling_contracts.loc[start]
    expiries = {d: e for d, e in ROLLING_EXPIRIES.items() if d != ROLLING_DELIVERIES[0]}

    forward = forward_rolling_structure(
        curve, expiries, FLY, start=start, on_missing_expiry="truncate"
    )

    assert forward.empty
    assert forward.name == "M1-2M2+M3"
    assert forward.dtype == "float64"


def test_forward_truncate_on_a_complete_schedule_changes_nothing(rolling_contracts):
    start = pd.Timestamp("2026-10-01")
    curve = rolling_contracts.loc[start]

    pd.testing.assert_series_equal(
        forward_rolling_structure(
            curve, ROLLING_EXPIRIES, FLY, start=start, on_missing_expiry="truncate"
        ),
        forward_rolling_structure(curve, ROLLING_EXPIRIES, FLY, start=start),
    )


def test_forward_rejects_an_unknown_missing_expiry_policy(rolling_contracts):
    with pytest.raises(ValueError, match="on_missing_expiry"):
        forward_rolling_structure(
            rolling_contracts.loc["2026-10-01"], ROLLING_EXPIRIES, FLY,
            start=pd.Timestamp("2026-10-01"), on_missing_expiry="skip",
        )


# --------------------------------------------------------------------------
# recent_structure goes through the single engine


def _recent_structure_1_1_0(contracts, structure_combo, roll_days=0):
    """``recent_structure`` as released in 1.1.0: prebuilt legs, subtracted."""
    contracts = forwards.convert_columns_to_date(contracts)
    months = list({m for combo in structure_combo for m in combo})
    legs = generate_multiple_continuous_series(contracts, months=months, roll_days=roll_days)
    dfs = []
    for mx, my in structure_combo:
        df = pd.concat([legs[f"M{mx}"], legs[f"M{my}"]], axis=1)
        df[f"M{mx}-M{my}"] = df[f"M{mx}"].sub(df[f"M{my}"]).dropna()
        dfs.append(df[[f"M{mx}-M{my}"]].dropna(how="all", axis="rows"))
    return pd.concat(dfs, axis=1).dropna(how="all", axis="rows")


@pytest.mark.parametrize("roll_days", [0, 2])
def test_recent_structure_is_unchanged_on_the_cl_fixture(contracts, roll_days):
    combos = [[1, 2], [1, 3], [1, 6], [1, 12]]

    _assert_identical(
        forwards.recent_structure(contracts, combos, roll_days=roll_days),
        _recent_structure_1_1_0(contracts, combos, roll_days=roll_days),
    )


def test_recent_structure_is_unchanged_on_a_rolling_board(rolling_contracts):
    combos = [[1, 2], [2, 4], [1, 3]]

    _assert_identical(
        forwards.recent_structure(rolling_contracts, combos, roll_days=3),
        _recent_structure_1_1_0(rolling_contracts, combos, roll_days=3),
    )
