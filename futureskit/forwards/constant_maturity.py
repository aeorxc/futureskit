"""Roll-safe constant-maturity grids built from contract matrices."""

from __future__ import annotations

import warnings
from collections.abc import Hashable, Mapping
from typing import NamedTuple

import numpy as np
import pandas as pd

from futureskit.forwards._occupancy import (
    build_occupants,
    resolve_expiry_dates,
    values_from_occupants,
)
from futureskit.forwards.rollspec import Adjustment, RollSpec, resolve_roll_spec
from futureskit.forwards.schema import validate_contract_matrix


class ConstantMaturityGrid(NamedTuple):
    """Levels, same-column changes, and column identities by tenor."""

    levels: pd.DataFrame
    changes: pd.DataFrame
    contracts: pd.DataFrame


def constant_maturity_grid(
    contracts: pd.DataFrame,
    expiry_dates: Mapping[Hashable, pd.Timestamp] | None = None,
    n_tenors: int = 12,
    roll_days: int | None = None,
    *,
    roll_spec: RollSpec | None = None,
) -> ConstantMaturityGrid:
    """Build an M1..Mn grid preserving column identity through missing values.

    A column is live through its roll date. A ``RollSpec`` may start the grid
    at a deeper eligible contract and restrict eligible delivery months.
    Legacy ``roll_days`` steps backward from the last quoted observation on or
    before expiry. Changes are calculated
    within each column before tenor assignment, so rolls introduce no gap.
    Explicit expiry mappings must cover every column. Inferred expiries use
    each column's last valid observation, but only where that observation falls
    before the end of the sample: a column quoted through the last printing day
    infers ``BEYOND_SAMPLE``, so it is live to the last row and does not roll,
    unless its label is anchored on a month start whose month ended before the
    last printing day, in which case the inferred expiry is capped at the last
    day of that month. An all-NaN column infers ``NaT`` and is never selected
    without an explicit expiry.
    """
    validate_contract_matrix(contracts)
    if not isinstance(n_tenors, int) or isinstance(n_tenors, bool) or n_tenors < 1:
        raise ValueError("n_tenors must be a positive integer")
    spec = resolve_roll_spec(roll_spec, roll_days)
    if spec.adjustment is not Adjustment.NONE:
        raise NotImplementedError(
            "constant_maturity_grid currently supports only Adjustment.NONE"
        )

    if expiry_dates is None and spec.anchor_expiries is None:
        warnings.warn(
            "Inferring expiry dates from each contract's last valid observation: "
            "frozen post-expiry prints can inflate inferred expiry dates. A "
            "contract still quoted at the end of the sample has no observable "
            "expiry at all; it infers BEYOND_SAMPLE and is held live through the "
            "last observation, unless its label is anchored on a month start "
            "whose month ended earlier, in which case it expires at that month "
            "end.",
            UserWarning,
            stacklevel=2,
        )
    resolved_expiries = resolve_expiry_dates(
        contracts, expiry_dates, spec.anchor_expiries
    )

    tenors = [f"M{number}" for number in range(spec.depth, spec.depth + n_tenors)]
    occupants = build_occupants(
        contracts,
        resolved_expiries,
        n_tenors,
        spec.roll_rule.days,
        depth=spec.depth,
        month_filter=spec.month_filter,
    )
    levels = pd.DataFrame(
        values_from_occupants(contracts.to_numpy(dtype=float), occupants),
        index=contracts.index,
        columns=tenors,
    )
    changes = pd.DataFrame(
        values_from_occupants(contracts.diff().to_numpy(dtype=float), occupants),
        index=contracts.index,
        columns=tenors,
    )
    identities = contracts.columns.to_numpy()
    if isinstance(contracts.columns, pd.DatetimeIndex):
        identity_values = np.full(
            occupants.shape, np.datetime64("NaT", "ns"), dtype="datetime64[ns]"
        )
    else:
        identity_values = np.full(occupants.shape, None, dtype=object)
    rows, slots = np.nonzero(occupants >= 0)
    identity_values[rows, slots] = identities[occupants[rows, slots]]
    occupying_contracts = pd.DataFrame(
        identity_values, index=contracts.index, columns=tenors
    )

    for frame in (levels, changes, occupying_contracts):
        frame.columns.name = "tenor"
    return ConstantMaturityGrid(levels, changes, occupying_contracts)
