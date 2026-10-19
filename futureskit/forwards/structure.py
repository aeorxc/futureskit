import warnings
from collections.abc import Callable, Hashable, Mapping
from typing import Literal

import numpy as np
import pandas as pd

from futureskit.forwards._occupancy import build_occupants, resolve_expiry_dates
from futureskit.forwards.schema import validate_contract_matrix


def rolling_structure(
    contracts: pd.DataFrame,
    weights: Mapping[int, float],
    expiry_dates: Mapping[Hashable, object] | None = None,
    roll_days: int = 0,
    *,
    trim: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
) -> pd.Series:
    """Stitch a weighted tenor structure (spread, fly, ...) along the roll.

    ``weights`` maps tenor number to leg weight: ``{1: 1, 6: -1}`` is M1-M6,
    ``{1: 1, 2: -2, 3: 1}`` the M1-M2-M3 fly. Tenors are resolved by the same
    occupant engine as :func:`generate_series`, so with ``trim=None`` the
    result equals the weighted sum of those continuous tenors.

    ``trim`` exists because expiry noise belongs to a *fixed* structure, not to
    the stitched one: a spread whose front leg is days from expiry is noisy
    whichever tenor it occupies. Every fixed instance the roll visits is built
    over the whole frame index as one column of a wide frame — columns are a
    ``MultiIndex`` of leg deliveries named ``M<tenor>`` — and that frame is
    passed to ``trim``, which returns it with noisy cells set to NaN (for
    example ``commodutil.stats.trim_expiry_noise``). Each row then takes the
    trimmed value of the instance occupying it. The rule is the caller's:
    futureskit decides which instance occupies a row, never which prints are
    noise. A row whose legs are not all occupied is NaN.
    """
    validate_contract_matrix(contracts)
    tenors = sorted(weights)
    if not tenors or any(
        not isinstance(t, int) or isinstance(t, bool) or t < 1 for t in tenors
    ):
        raise ValueError("weights must map positive integer tenors to weights")

    resolved = resolve_expiry_dates(contracts, expiry_dates)
    legs = build_occupants(contracts, resolved, max(tenors), roll_days)[
        :, [t - 1 for t in tenors]
    ]
    occupied = (legs >= 0).all(axis=1)
    instances = np.unique(legs[occupied], axis=0)

    values = contracts.to_numpy(dtype=float)
    wide = pd.DataFrame(
        np.column_stack(
            [sum(weights[t] * values[:, p] for t, p in zip(tenors, row)) for row in instances]
        )
        if len(instances)
        else np.empty((len(contracts), 0)),
        index=contracts.index,
        columns=pd.MultiIndex.from_tuples(
            [tuple(contracts.columns[row]) for row in instances],
            names=[f"M{t}" for t in tenors],
        ),
    )
    if trim is not None:
        wide = trim(wide)

    result = np.full(len(contracts), np.nan)
    for row in instances:
        rows = (legs == row).all(axis=1)
        key = tuple(contracts.columns[row])
        result[rows] = wide[key].to_numpy(dtype=float)[rows]
    label = "".join(
        f"{'-' if weights[t] < 0 else '+'}{'' if abs(weights[t]) == 1 else f'{abs(weights[t]):g}'}M{t}"
        for t in tenors
    ).removeprefix("+")
    return pd.Series(result, index=contracts.index, name=label)


def generate_structure_series(contracts: pd.DataFrame,
                              mx: int = 1,
                              my: int = 2,
                              roll_days: int = 0,
                              mx_df: pd.DataFrame = None,
                              my_df: pd.DataFrame = None,
                              expiry_dates: Mapping[Hashable, object] | None = None
                              ) -> pd.DataFrame:
    """
    Rolling ``M{mx}-M{my}`` spread: :func:`rolling_structure` with weights
    ``{mx: 1, my: -1}``, in one column labelled ``"M{mx}-M{my}"`` with rows
    where either leg is missing dropped.

    ``expiry_dates`` is passed through to :func:`rolling_structure`. Leaving it
    ``None`` falls back to inferring each expiry from the frame, which is a
    fallback rather than a feature: prefer a curated map in any durable
    consumer so the roll dates are asserted, not guessed.

    ``mx_df`` and ``my_df`` are deprecated and will be removed in 2.0: pass
    ``contracts`` and let :func:`rolling_structure` build the legs. Supplied
    together they still subtract the prebuilt series directly, ignoring
    ``expiry_dates``, so their dtype and column-axis name pass through.
    """

    colname = f"M{mx}-M{my}"

    if mx_df is not None or my_df is not None:
        warnings.warn(
            "generate_structure_series(mx_df=..., my_df=...) is deprecated and "
            "will be removed in futureskit 2.0; pass contracts instead",
            DeprecationWarning,
            stacklevel=2,
        )
    if mx_df is not None and my_df is not None:
        df = pd.concat([mx_df, my_df], axis=1)
        df[colname] = df[f"M{mx}"].sub(df[f"M{my}"]).dropna()
        return df[[colname]].dropna(how="all", axis="rows")

    if mx == my:
        # A dict cannot hold both legs; 1.0.5 raised here too.
        raise ValueError(f"mx and my must differ; got {mx}")
    spread = rolling_structure(
        contracts, {mx: 1, my: -1}, expiry_dates=expiry_dates, roll_days=roll_days
    )
    return spread.dropna().to_frame(colname)


def forward_rolling_structure(
    curve: pd.Series,
    expiry_dates: Mapping[Hashable, object],
    weights: Mapping[int, float],
    roll_days: int = 0,
    *,
    start: pd.Timestamp,
    horizon_months: int = 24,
    on_missing_expiry: Literal["raise", "truncate"] = "raise",
) -> pd.Series:
    """Project a :func:`rolling_structure` forward from one curve.

    ``curve`` is today's forward curve: one price per delivery, indexed by the
    same opaque identities as ``expiry_dates`` and ordered by delivery, like
    the columns of a contracts frame. Every curve entry needs an expiry, and
    ``expiry_dates=None`` is rejected: inference would read the flat quotes
    below as contracts that never expire.

    ``on_missing_expiry`` says what to do with a curve entry that has no
    expiry. ``"raise"`` (the default) rejects a curve entry absent from
    ``expiry_dates``. ``"truncate"`` cuts the curve at the first entry, in
    curve order, whose expiry is absent or null, and projects what precedes
    it: a delivery that cannot be placed cannot be skipped either, since
    skipping it would shift every later delivery into an earlier tenor. If
    nothing precedes it the result is empty.

    The projection holds the curve flat and lets the tenors roll through it:
    the result is :func:`rolling_structure` over a contracts frame that repeats
    ``curve`` on ``start`` and on every business day up to ``horizon_months``
    later. The roll convention is therefore the history's - live through
    ``roll_days`` trading days before the last trading day on or before
    expiry, inclusive - with Monday to Friday as the trading days past
    ``start``, the same extension the history applies to an expiry beyond its
    sample. Exchange holidays are unknown, so a holiday inside the window
    projects a roll one day late. For a history built from the same expiries
    and printing through ``start``, the forward's first value equals the
    history's last unless a roll falls between them.

    The result is named like :func:`rolling_structure` (``"M1-2M2+M3"``),
    indexed by business day and excludes ``start``. Days on which a leg has
    run off the end of the curve, or reads a missing price, are absent; an
    empty series means nothing can be projected.

    >>> import pandas as pd
    >>> from futureskit import forwards
    >>> curve = pd.Series(
    ...     [70.0, 69.0, 68.5, 68.2],
    ...     index=pd.to_datetime(["2026-12-01", "2027-01-01", "2027-02-01", "2027-03-01"]),
    ... )
    >>> expiries = dict(zip(curve.index, pd.to_datetime(
    ...     ["2026-10-30", "2026-11-30", "2026-12-31", "2027-01-29"])))
    >>> fly = forwards.forward_rolling_structure(
    ...     curve, expiries, {1: 1, 2: -2, 3: 1},
    ...     start=pd.Timestamp("2026-10-07"), horizon_months=2,
    ... )
    >>> fly.name
    'M1-2M2+M3'
    >>> round(float(fly["2026-10-30"]), 2), round(float(fly["2026-11-02"]), 2)
    (0.5, 0.2)
    >>> fly.index[-1].date()  # the fly needs a third live delivery
    datetime.date(2026, 11, 30)
    """
    if expiry_dates is None:
        raise ValueError("forward_rolling_structure requires expiry_dates")
    if on_missing_expiry not in ("raise", "truncate"):
        raise ValueError(
            f"on_missing_expiry must be 'raise' or 'truncate'; got {on_missing_expiry!r}"
        )
    if on_missing_expiry == "truncate":
        known = [pd.notna(expiry_dates.get(delivery)) for delivery in curve.index]
        if not all(known):
            curve = curve.iloc[: known.index(False)]
            expiry_dates = {delivery: expiry_dates[delivery] for delivery in curve.index}
    start = pd.Timestamp(start)
    days = pd.bdate_range(
        start + pd.Timedelta(days=1), start + pd.DateOffset(months=horizon_months)
    )
    index = pd.DatetimeIndex([start]).append(days)
    flat = pd.DataFrame(
        np.tile(curve.to_numpy(dtype=float), (len(index), 1)),
        index=index,
        columns=curve.index,
    )
    projected = rolling_structure(flat, weights, expiry_dates, roll_days).dropna()
    return projected.loc[projected.index > start]
