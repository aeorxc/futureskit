"""Define the explicit input contract for futureskit forward calculations.

A forwards frame is a wide pandas DataFrame whose columns are unique instrument
or tenor identities in the order they participate in the curve.  Labels are
deliberately opaque: futureskit does not require delivery-month timestamps or
parse vendor notation here.  Its observation index is a timezone-naive,
strictly increasing, unique DatetimeIndex, and its values are numeric prices.

Expiry dates are either ``None`` or a mapping from the frame's exact column
labels to timezone-naive, datetime-like expiry dates.
``None`` makes continuous-series code derive expiries from the last populated
observation in each contract, and only where that observation falls before the
end of the sample; a contract quoted through it was not observed to expire and
infers ``forwards.BEYOND_SAMPLE`` instead, which is an ordinary Timestamp and
validates as one.  A column labelled with a month start whose month ended
before the last printing day is capped at that month's last day, because a
monthly contract cannot be live once its delivery month is over.  Labels stay
opaque here: schema validation neither requires nor interprets a delivery
month, and any other label shape is left uncapped.  When a mapping is supplied but a delivery key
is missing, ``validate_expiry_dates`` returns the missing column identity so
the consuming calculation can reject the incomplete schedule.

``roll_days`` positions the roll date, and the outgoing contract is live
through that date **inclusive**.  The anchor is the last printing day on or
before the delivery's expiry; the roll date sits ``roll_days`` printing days
before that anchor; the incoming delivery is selected from the next printing
day onward.  So ``roll_days=0`` rolls out of the outgoing contract after the
anchor itself, not on it.  Printing days are rows on which at least one
contract quoted, so a row where the whole board is NaN is skipped when
counting back rather than consuming one of the ``roll_days``.

Marketplace ``adjust_contract(rollDays=N)`` matches ``roll_days=N`` exactly at
``N=0`` and ``N=1``, sharing the inclusive-roll-date semantics.  For larger
``N`` Marketplace subtracts *calendar* days and snaps forward to the next
trading day, so its expiry-to-roll distance is not a fixed trading-day offset
and no exact mapping to ``roll_days`` exists.  futureskit's offset is always
exactly ``N`` printing days.

New continuous-series code should carry the same convention through the
data-only ``RollSpec`` value object. Schema validation remains independent of
roll policy and of any delivery-month filtering requested by a caller.
"""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype


def _is_timestamp_like(value: Any) -> bool:
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return not pd.isna(value)
    dtype = getattr(value, "dtype", None)
    return dtype is not None and is_datetime64_any_dtype(dtype) and not pd.isna(value)


def _is_timezone_naive(value: Any) -> bool:
    return _is_timestamp_like(value) and pd.Timestamp(value).tz is None


def validate_contract_matrix(
    df: pd.DataFrame, *, strict: bool = True
) -> list[str] | None:
    """Validate the commodity-neutral forwards-frame shape.

    Column order defines curve order; labels themselves have no required type
    or calendar meaning.

    With ``strict=True``, raise one ``ValueError`` containing every violation.
    With ``strict=False``, return the violations instead.  A valid strict
    validation returns ``None``.
    """
    if not isinstance(df, pd.DataFrame):
        violations = ["input must be a pandas DataFrame"]
    else:
        violations = []
        if not df.columns.is_unique:
            violations.append("columns must be unique")
        if not isinstance(df.index, pd.DatetimeIndex):
            violations.append("index must be a pandas DatetimeIndex")
        else:
            if not df.index.is_monotonic_increasing:
                violations.append("index must be sorted in ascending observation order")
            if not df.index.is_unique:
                violations.append("index must be unique")
            if df.index.tz is not None:
                violations.append("index must be timezone-naive")
        if not all(
            is_numeric_dtype(dtype) and not is_bool_dtype(dtype) for dtype in df.dtypes
        ):
            violations.append("values must be numeric")

    if strict and violations:
        raise ValueError("Invalid forwards frame: " + "; ".join(violations))
    return None if strict else violations


def validate_expiry_dates(
    expiry_dates: Mapping[Any, Any] | None, df: pd.DataFrame | None = None
) -> list[Any]:
    """Validate an expiry map and list frame columns missing from it.

    ``None`` is valid and selects data-derived expiries, so it has no missing
    column warning. Invalid values raise ``ValueError``. Keys are opaque frame
    identities. When ``df`` is provided, this function returns its columns
    absent from a valid supplied map; missing columns do not raise here.
    """
    if expiry_dates is None:
        return []
    if not isinstance(expiry_dates, Mapping):
        raise ValueError("expiry_dates must be a mapping or None")

    invalid_values = [
        value for value in expiry_dates.values() if not _is_timestamp_like(value)
    ]
    invalid_value_timezones = [
        value
        for value in expiry_dates.values()
        if _is_timestamp_like(value) and not _is_timezone_naive(value)
    ]
    violations = []
    if invalid_values:
        violations.append("expiry_dates values must be Timestamp-like")
    if invalid_value_timezones:
        violations.append("expiry_dates values must be timezone-naive")
    if violations:
        raise ValueError("Invalid expiry dates: " + "; ".join(violations))

    if df is None:
        return []
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a pandas DataFrame")

    return [delivery for delivery in df.columns if delivery not in expiry_dates]
