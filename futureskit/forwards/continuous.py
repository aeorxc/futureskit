from collections.abc import Hashable, Mapping, Sequence

import numpy as np
import pandas as pd

from futureskit.forwards._occupancy import (
    build_occupants,
    resolve_expiry_dates,
    values_from_occupants,
)
from futureskit.forwards.rollspec import Adjustment, RollSpec, resolve_roll_spec
from futureskit.forwards.schema import validate_contract_matrix


def _occupied_rolls(
    path: np.ndarray,
    index: pd.DatetimeIndex,
) -> list[tuple[int, int, pd.Timestamp]]:
    """Return the roll pairs of one tenor's own occupancy path.

    Roll dates are read from the path produced by ``build_occupants`` rather
    than recomputed from the outgoing delivery's expiry. A deeper tenor
    switches when the tenor slot ahead of it expires, not when its own
    delivery does, so recomputing gave every tenor the front month's roll
    dates and gaps. The inclusive-roll convention means the outgoing delivery
    is still live on the roll date, so the roll date is the last observation
    it occupied.
    """
    rolls = []
    for row in range(1, len(path)):
        outgoing, incoming = int(path[row - 1]), int(path[row])
        if outgoing < 0 or incoming < 0 or outgoing == incoming:
            continue
        rolls.append((outgoing, incoming, pd.Timestamp(index[row - 1])))
    return rolls


def _roll_value(
    contracts: pd.DataFrame,
    outgoing: int,
    incoming: int,
    roll_date: pd.Timestamp,
    *,
    ratio: bool,
) -> float:
    """Return one incoming-vs-outgoing gap, with documented neutral values."""
    row = contracts.index.get_loc(roll_date)
    outgoing_price = contracts.iloc[row, outgoing]
    incoming_price = contracts.iloc[row, incoming]
    if pd.isna(outgoing_price) or pd.isna(incoming_price):
        return 1.0 if ratio else 0.0
    if ratio:
        for role, column, price in (
            ("outgoing", outgoing, outgoing_price),
            ("incoming", incoming, incoming_price),
        ):
            if price <= 0:
                raise ValueError(
                    f"ratio adjustment is undefined on roll date {roll_date.date()}: "
                    f"{role} contract {contracts.columns[column]!r} has "
                    f"non-positive price {float(price)!r}"
                )
    return float(
        incoming_price / outgoing_price if ratio else incoming_price - outgoing_price
    )


def _apply_axis_adjustment(
    result: pd.DataFrame,
    contracts: pd.DataFrame,
    path: np.ndarray,
    rolls: list[tuple[int, int, pd.Timestamp]],
    adjustment: Adjustment,
    mask_adjust: pd.DataFrame,
) -> pd.DataFrame:
    """Apply cumulative spread or ratio math in the requested direction."""
    backward = adjustment in {
        Adjustment.BACKWARD_SPREAD,
        Adjustment.BACKWARD_RATIO,
    }
    ratio = adjustment in {
        Adjustment.BACKWARD_RATIO,
        Adjustment.FORWARD_RATIO,
    }
    for outgoing, incoming, roll_date in rolls:
        value = _roll_value(contracts, outgoing, incoming, roll_date, ratio=ratio)
        if not backward:
            if ratio:
                value = 1.0 / value
            else:
                value = -value
        column = outgoing if backward else incoming
        mask_adjust.iloc[path == column, column] = value

    propagated = mask_adjust.bfill() if backward else mask_adjust.ffill()
    if ratio:
        factors = propagated.prod(axis=1, min_count=1).fillna(1.0)
        return result.mul(factors, axis=0)
    offsets = propagated.sum(axis=1, min_count=1).fillna(0.0)
    return result.add(offsets, axis=0)


def _apply_linear_blend(
    result: pd.DataFrame,
    contracts: pd.DataFrame,
    path: np.ndarray,
    rolls: list[tuple[int, int, pd.Timestamp]],
    interpolate_days: int,
    mask_adjust: pd.DataFrame,
) -> pd.DataFrame:
    """Blend each occupied outgoing/incoming pair over the final observations.

    ``PERPETUAL`` remaining-observation weights and ``INTERPOLATED`` straight
    linear weights are the same observation-based ramp: across an N-row window
    the incoming weights are ``1/N, ..., N/N``. The inclusive roll date is the
    final row and is therefore entirely the incoming contract.
    Blends propagate NaN from either contract whenever its weight is non-zero.
    """
    blended = result.copy()
    trading_observations = contracts.index.isin(contracts.dropna(how="all").index)
    for outgoing, incoming, roll_date in rolls:
        positions = np.flatnonzero(
            (path == outgoing) & trading_observations & (contracts.index <= roll_date)
        )[-interpolate_days:]
        if not len(positions):
            continue
        remaining = np.arange(len(positions) - 1, -1, -1, dtype=float)
        outgoing_weights = remaining / len(positions)
        incoming_weights = 1.0 - outgoing_weights
        outgoing_prices = contracts.iloc[positions, outgoing].to_numpy(dtype=float)
        incoming_prices = contracts.iloc[positions, incoming].to_numpy(dtype=float)
        outgoing_component = np.zeros(len(positions), dtype=float)
        incoming_component = np.zeros(len(positions), dtype=float)
        np.multiply(
            outgoing_prices,
            outgoing_weights,
            out=outgoing_component,
            where=outgoing_weights != 0,
        )
        np.multiply(
            incoming_prices,
            incoming_weights,
            out=incoming_component,
            where=incoming_weights != 0,
        )
        blended.iloc[positions, 0] = outgoing_component + incoming_component
        mask_adjust.iloc[positions, outgoing] = incoming_weights
    return blended


def generate_series(
    df: pd.DataFrame,
    expiry_dates: Mapping[Hashable, object] | None = None,
    roll_days: int | None = None,
    front_month: int | Sequence[int] | None = None,
    back_adjust: bool | None = None,
    *,
    roll_spec: RollSpec | None = None,
) -> pd.DataFrame:
    """Create continuous forward levels using a :class:`RollSpec`.

    ``roll_days``, ``front_month``, and ``back_adjust`` remain the legacy
    parameterization. They cannot be mixed with ``roll_spec``. The legacy
    ``roll_days=N`` convention is preserved exactly: the outgoing contract is
    live on the inclusive roll date. Marketplace ``rollDays=N`` matches
    ``roll_days=N`` exactly at ``N=0`` and ``N=1``, sharing those semantics;
    for larger ``N`` Marketplace subtracts calendar days and snaps forward to
    the next trading day, so no exact mapping exists above one.

    Spread adjustments use the incoming-minus-outgoing roll-date gap; ratio
    adjustments use incoming divided by outgoing. Backward modes propagate the
    value into history, while forward modes propagate its inverse direction
    into the future. If either roll-date price is NaN, that roll is neutral
    (zero for spreads, one for ratios). Ratio adjustments require both prices
    to be positive and otherwise raise :class:`ValueError` naming the roll
    date, offending contract, and price; use spread modes for non-positive
    prices.

    ``PERPETUAL`` and ``INTERPOLATED`` are aliases for the same linear blend
    over ``interpolate_days`` observations ending on the inclusive roll date.
    Each roll follows the occupied path, including depth and month filters;
    later physical frame columns are never assumed to be adjacent. Every
    requested tenor is adjusted along its own occupancy path, so a deeper
    tenor takes its own roll gaps rather than the front month's.

    ``attrs["mask_switch"]`` reports the occupancy the engine resolved, one row
    per observation holding the frame-column position of each tenor from M1
    outward. It is not reindexed to the tenors returned: with a scalar
    ``front_month=k`` the frame carries only ``Mk``, while each ``mask_switch``
    row still spans M1 through Mk, so element 0 is M1's delivery rather than
    the returned tenor's, which is element ``k - 1``.
    """
    explicit_spec = roll_spec is not None
    if explicit_spec and (front_month is not None or back_adjust is not None):
        raise ValueError("roll_spec cannot be combined with front_month or back_adjust")
    spec = resolve_roll_spec(roll_spec, roll_days)
    if explicit_spec:
        months = [spec.depth]
    else:
        selected = 1 if front_month is None else front_month
        months = [selected] if isinstance(selected, int) else list(selected)
    if not months or any(
        not isinstance(month, int) or isinstance(month, bool) or month < 1
        for month in months
    ):
        raise ValueError("front_month values must be positive integers")

    legacy_back_adjust = False if back_adjust is None else back_adjust
    if not isinstance(legacy_back_adjust, bool):
        raise TypeError("back_adjust must be a boolean")
    adjustment = (
        spec.adjustment
        if explicit_spec
        else (Adjustment.BACKWARD_SPREAD if legacy_back_adjust else Adjustment.NONE)
    )
    if spec.depth > 1 and adjustment not in {
        Adjustment.NONE,
        Adjustment.BACKWARD_SPREAD,
    }:
        raise NotImplementedError(
            f"depth>1 adjustment is not yet supported for this mode: "
            f"{adjustment.value!r}"
        )
    contracts = df.copy()
    validate_contract_matrix(contracts)

    resolved_expiries = resolve_expiry_dates(
        contracts, expiry_dates, spec.anchor_expiries
    )
    if explicit_spec:
        occupants = build_occupants(
            contracts,
            resolved_expiries,
            1,
            spec.roll_rule.days,
            depth=spec.depth,
            month_filter=spec.month_filter,
        )
        selected_columns = [0]
    else:
        occupants = build_occupants(
            contracts, resolved_expiries, max(months), spec.roll_rule.days
        )
        selected_columns = (np.asarray(months) - 1).tolist()
    selected = values_from_occupants(contracts.to_numpy(dtype=float), occupants)
    result = pd.DataFrame(
        selected[:, selected_columns],
        index=contracts.index,
        columns=[f"M{month}" for month in months],
    )

    if adjustment is not Adjustment.NONE:
        adjusted = []
        for tenor, label in zip(selected_columns, result.columns):
            path = occupants[:, tenor]
            rolls = _occupied_rolls(path, contracts.index)
            mask_adjust = pd.DataFrame(
                index=contracts.index, columns=contracts.columns, dtype=float
            )
            column = result[[label]]
            if adjustment in {
                Adjustment.BACKWARD_SPREAD,
                Adjustment.FORWARD_SPREAD,
                Adjustment.BACKWARD_RATIO,
                Adjustment.FORWARD_RATIO,
            }:
                column = _apply_axis_adjustment(
                    column, contracts, path, rolls, adjustment, mask_adjust
                )
            elif adjustment in {Adjustment.PERPETUAL, Adjustment.INTERPOLATED}:
                column = _apply_linear_blend(
                    column,
                    contracts,
                    path,
                    rolls,
                    spec.interpolate_days,
                    mask_adjust,
                )
            adjusted.append(column)
        result = pd.concat(adjusted, axis=1)

    # A nested list, not the array: pandas compares ``attrs`` with ``==`` in
    # ``__finalize__``, and an array there makes the result uncombinable.
    result.attrs["mask_switch"] = occupants.tolist()
    return result


def generate_multiple_continuous_series(
    contracts: pd.DataFrame,
    months: Sequence[int] | None = None,
    roll_days: int | None = None,
    expiry_dates: Mapping[Hashable, object] | None = None,
    *,
    roll_spec: RollSpec | None = None,
) -> pd.DataFrame:
    """Build one or more continuous levels; prefer ``roll_spec`` for new code."""
    if roll_spec is not None and months is not None:
        raise ValueError("roll_spec and months are mutually exclusive")
    selected = [1, 2] if months is None and roll_spec is None else months
    df = generate_series(
        contracts,
        expiry_dates=expiry_dates,
        front_month=selected,
        roll_days=roll_days,
        roll_spec=roll_spec,
    )
    return df
