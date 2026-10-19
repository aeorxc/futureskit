"""Averaging a strip's legs, and deciding how many of them must be there.

A strip is the average of its deliveries: a calendar is twelve months, a
half-year or season six, a quarter three. The question this module answers is
what to do on an observation date when not all of them are quoted.

The rule is that a strip requires every leg that is **live** on that date, and
a leg is live between the day it lists and the day it expires. A delivery that
has already expired is not missing data, it is simply over, and demanding it
would make a calendar go dark for the whole of its final year. A delivery that
has not started trading yet is not missing data either, and demanding it would
make a calendar go dark for the whole of its birth — the months of a far year
list one by one, so requiring all twelve from the first quote costs the strip
every observation until the last month arrives. A delivery that is listed and
unexpired but has no quote *is* missing data, and averaging around it publishes
a number that is not the strip. So CAL 2020 on 2020-01-02, with January expired
and the remaining eleven months quoted, is the eleven-month balance of the
year; the same strip on a date when a live month has no print is ``NaN``.

Liveness is read from the data, never from a calendar, which is the package's
second invariant. A leg is listed at date ``t`` when its first valid
observation falls on or before ``t``. A leg is expired at ``t`` when its last
valid observation falls strictly before ``t`` — the same last-observation
inference
:func:`futureskit.forwards.infer_expiry_dates` applies when no expiry map is
given, and the caller can supply a curated map instead exactly as the
continuous-series entry points allow. That inference proves an expiry only
where the leg fell silent before the end of the sample: a leg still quoted on
the last printing day infers :data:`futureskit.forwards.BEYOND_SAMPLE` and is
live through the last row, so a strip read over a short window is the strip
rather than a board of legs that all appear to have just expired. A leg whose
label is anchored on a month start whose month ended before the last printing
day is capped there instead, so a venue's post-expiry prints do not hold a dead leg in a
strip. A delivery that was never observed is never live, and therefore never
required.
"""

from collections.abc import Hashable, Mapping

import numpy as np
import pandas as pd

from futureskit.forwards._occupancy import infer_expiry_dates, resolve_expiry_dates


def strip_mean(
    legs: pd.DataFrame,
    expiry_dates: Mapping[Hashable, object] | None = None,
    min_legs: int | None = None,
) -> pd.Series:
    """Average a strip's legs, requiring every live leg unless told otherwise.

    :param legs: the strip's delivery columns, in any order.
    :param expiry_dates: a curated expiry per leg. ``None`` infers each leg's
        expiry from its own last valid observation.
    :param min_legs: how many of the live legs must carry a quote. ``None``
        requires all of them. An explicit integer is a deliberate lowering of
        the bar: ``min_legs=1`` averages whatever is live and quoted.
    """
    if legs.shape[1] == 0:
        return pd.Series(np.nan, index=legs.index, dtype=float)

    expiries = (
        infer_expiry_dates(legs)
        if expiry_dates is None
        else resolve_expiry_dates(legs, expiry_dates)
    )
    # Build both bounds through pandas so a never-observed leg's ``NaT`` (and the
    # ``None`` that ``first_valid_index`` returns for an all-NaN column) survive
    # as ``NaT``. ``np.array([...], dtype="datetime64[ns]")`` rejects the float
    # form of ``NaT`` on recent numpy/pandas and raised for every strip with an
    # empty leg instead of letting the liveness mask exclude it.
    expiry_row = pd.to_datetime(
        pd.Series([expiries[column] for column in legs.columns], dtype="object")
    ).to_numpy(dtype="datetime64[ns]")
    listing_row = pd.to_datetime(
        pd.Series(
            [legs[column].first_valid_index() for column in legs.columns],
            dtype="object",
        )
    ).to_numpy(dtype="datetime64[ns]")
    observed = legs.index.to_numpy(dtype="datetime64[ns]")[:, None]

    # Live is bounded at both ends: listed, and not yet expired. A leg that has
    # not started trading is not a leg with a missing quote, so requiring it
    # would blank the strip for the whole of its birth. NaT compares False at
    # either bound, so a never-observed leg is never live and never required —
    # the same rule the occupancy engine applies to a tenor slot.
    live = (listing_row[None, :] <= observed) & (observed <= expiry_row[None, :])

    values = legs.to_numpy(dtype=float)
    quoted = live & ~np.isnan(values)
    quoted_count = quoted.sum(axis=1)
    required = live.sum(axis=1) if min_legs is None else min_legs

    total = np.where(quoted, values, 0.0).sum(axis=1)
    mean = np.divide(
        total,
        quoted_count,
        out=np.full(len(legs), np.nan),
        where=quoted_count > 0,
    )
    return pd.Series(np.where(quoted_count >= required, mean, np.nan), index=legs.index)
