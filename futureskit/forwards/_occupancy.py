"""Canonical forwards-column-to-tenor assignment."""

from collections.abc import Hashable, Mapping

import numpy as np
import pandas as pd

from futureskit.forwards.schema import _is_timestamp_like, validate_expiry_dates
from futureskit.forwards.util import determine_roll_date


#: The expiry of a contract observed to be alive at the end of the sample.
#:
#: Last-observation inference can only prove an expiry it saw happen: a column
#: that fell silent while the rest of the board carried on. A column still
#: quoted on the last printing day was not observed to expire at all, and the
#: end of the sample is not its expiry — on a short window that reading would
#: declare the whole board expired on the final row.
#:
#: This constant says "alive past the end of this sample" in the one vocabulary
#: an expiry map has. It is a real, timezone-naive Timestamp, so it validates,
#: sorts and compares like any other expiry, and the roll engine returns it
#: unadjusted whatever ``roll_days`` is, so it never rolls in-sample. It is far
#: enough out to be unmistakable and near enough to leave room for the date
#: arithmetic a consumer may apply — unlike ``pd.Timestamp.max``, which
#: overflows on the first offset added to it.
#:
#: It is deliberately *not* ``NaT``. ``NaT`` already means "never observed,
#: therefore never live" and that rule is load-bearing; one token cannot mean
#: both "never selected" and "always selected".
BEYOND_SAMPLE = pd.Timestamp("2200-01-01")


def last_printing_day(contracts: pd.DataFrame) -> pd.Timestamp | None:
    """The last observation row on which any column printed, or ``None``.

    Rows where the whole board is NaN are not evidence of anything, so the
    sample ends at the last row that carries a quote.
    """
    printing_days = contracts.dropna(how="all").index
    return None if printing_days.empty else pd.Timestamp(printing_days[-1])


def delivery_month_end(identity: Hashable) -> pd.Timestamp | None:
    """The last calendar day of a month-start-anchored label, or ``None``.

    A forwards column label is deliberately opaque, and only one label shape
    names a delivery month: a date-like label anchored on the first day of a
    month at midnight, which is how a monthly board spells Aug-2026. Everything
    else returns ``None`` and is never capped — a vendor string, an integer, a
    tuple, and equally a *dated* label such as ``2026-08-15``. A dated label is
    a prompt point, a cargo date or a Dated Brent-style assessment, not a
    monthly delivery, and reading August out of it would cap an instrument that
    has no delivery month at all.

    This is grammar, not a calendar. It reads the label and nothing else: no
    expiry table, no exchange holiday calendar, no per-root rule.
    """
    if not _is_timestamp_like(identity):
        return None
    label = pd.Timestamp(identity)
    if label.day != 1 or label != label.normalize():
        return None
    return label.to_period("M").end_time.normalize()


def infer_expiry_dates(contracts: pd.DataFrame) -> dict[Hashable, pd.Timestamp]:
    """Infer each column identity's expiry from its last valid observation.

    Every column gets one of four answers, and the last two are the reason this
    function is not simply ``last_valid_index``:

    ``a date``
        The column's last valid observation falls **strictly before** the last
        printing day. It stopped trading while the board carried on, and that
        gap is the evidence of an expiry.

    :data:`BEYOND_SAMPLE`
        The column is still quoted on the last printing day and its delivery
        month has not ended by then. Nothing was observed to expire, so the
        column is alive past the end of the sample: live on every row, and it
        does not roll inside it.

    ``the last day of the delivery month``
        The column's label is anchored on a month start and that month ended
        before the last printing day, while inference on its own would have run past it.
        A monthly contract cannot be live once its delivery month is over, so
        the inferred expiry is capped there. This is what stops a venue that
        keeps publishing a terminal settlement after expiry — ICE cleared swaps
        do — from holding an expired delivery in M1: without the cap, an
        August swap still printing through a September window read as alive and
        a September observation selected an August delivery. The cap uses only
        the column label, never a calendar or an expiry table, and it never
        touches a curated entry. The capped date is a real expiry, so
        ``roll_days`` steps back from it exactly as from any other.

    ``NaT``
        The column has no valid observation at all. Under inference the data is
        the only evidence an instrument exists, so an unobserved column is
        never live and must not occupy a tenor slot. An explicit expiry map is
        the caller asserting the instrument exists, and there an all-NaN column
        keeps its slot.

    The middle case is the whole point on a windowed frame — a short
    observation range across a full board, which is the shape a live screen
    fetches. Taking the window's end for an expiry there fabricates one for
    almost every delivery on the board and rolls an uncurated front month out
    of M1 on the final row.
    """
    sample_end = last_printing_day(contracts)
    inferred: dict[Hashable, pd.Timestamp] = {}
    for delivery in contracts.columns:
        last_observation = contracts[delivery].last_valid_index()
        if last_observation is None or sample_end is None:
            inferred[delivery] = pd.NaT
            continue
        if pd.Timestamp(last_observation) < sample_end:
            expiry = pd.Timestamp(last_observation)
        else:
            expiry = BEYOND_SAMPLE
        month_end = delivery_month_end(delivery)
        # Only a month the sample outlived is evidence the contract rolled off.
        # A month still running on the last printing day caps nothing, so a
        # live front delivery keeps BEYOND_SAMPLE.
        if month_end is not None and month_end < sample_end:
            expiry = min(expiry, month_end)
        inferred[delivery] = expiry
    return inferred


def merge_expiry_dates(
    contracts: pd.DataFrame,
    curated: Mapping[Hashable, object] | None,
) -> dict[Hashable, pd.Timestamp]:
    """Fill the gaps in a curated expiry map from the frame's own observations.

    The result is keyed on the frame's columns, so it is directly usable as an
    ``expiry_dates`` argument: a curated entry wins for every column it covers,
    and any column it omits falls back to :func:`infer_expiry_dates`. Curated
    keys that name no column are ignored rather than widening the schedule.

    An uncurated column inherits whichever of the four answers
    :func:`infer_expiry_dates` gives it, and only one of them is not a valid
    ``expiry_dates`` argument. A column quoted through the sample takes
    :data:`BEYOND_SAMPLE`, an ordinary Timestamp, so on a windowed frame — the
    case where most of the board is uncurated and still live — the result
    passes straight back in. A column that is both uncurated and never observed
    keeps its inferred ``NaT``, and a schedule carrying one is rejected rather
    than guessed at. That is deliberate on both counts: ``NaT`` surfaces as a
    tenor that is never live rather than disappearing from the schedule and
    shifting every later contract into an earlier slot, and a curated map with
    a hole in it is a mistake worth raising on.
    """
    inferred = infer_expiry_dates(contracts)
    curated = curated or {}
    return {
        identity: pd.Timestamp(curated[identity])
        if identity in curated
        else inferred[identity]
        for identity in contracts.columns
    }


def resolve_expiry_dates(
    contracts: pd.DataFrame,
    expiry_dates: Mapping[Hashable, object] | None,
    anchor_expiries: Mapping[Hashable, object] | None = None,
) -> dict[Hashable, pd.Timestamp]:
    """Resolve and validate the schedule used to roll each frame column."""
    if anchor_expiries is not None and expiry_dates is not None:
        raise ValueError("anchor_expiries and expiry_dates are mutually exclusive")
    schedule = anchor_expiries if anchor_expiries is not None else expiry_dates
    if schedule is None:
        return infer_expiry_dates(contracts)
    missing = validate_expiry_dates(schedule, contracts)
    if missing:
        name = "anchor_expiries" if anchor_expiries is not None else "expiry_dates"
        raise ValueError(f"{name} is missing columns: {missing!r}")
    return {
        identity: pd.Timestamp(schedule[identity]) for identity in contracts.columns
    }


def build_occupants(
    contracts: pd.DataFrame,
    expiry_dates: Mapping[Hashable, pd.Timestamp],
    n_tenors: int,
    roll_days: int,
    *,
    depth: int = 1,
    month_filter: tuple[int, ...] | None = None,
) -> np.ndarray:
    """Return eligible forward-column positions from ``depth`` onward."""
    eligible_positions = np.arange(len(contracts.columns), dtype=int)
    if month_filter is not None:
        delivery_months = []
        for identity in contracts.columns:
            month = getattr(identity, "month", None)
            if not isinstance(month, int) or month not in range(1, 13):
                raise ValueError(
                    "month_filter requires date-like forward column identities"
                )
            delivery_months.append(month)
        eligible_positions = eligible_positions[
            np.isin(delivery_months, np.asarray(month_filter))
        ]

    trading_days = contracts.dropna(how="all").index
    roll_dates = np.array(
        [
            # A NaT expiry (never-observed column under inference) yields a
            # NaT roll date; NaT compares False below, so it is never live.
            # BEYOND_SAMPLE needs no special case: determine_roll_date returns
            # it unadjusted, so the column is live on every row.
            np.datetime64("NaT", "ns")
            if pd.isna(expiry_dates[delivery])
            else np.datetime64(
                determine_roll_date(
                    contracts,
                    expiry_dates[delivery],
                    roll_days,
                    trading_days,
                )
            )
            for delivery in contracts.columns
        ],
        dtype="datetime64[ns]",
    )
    occupants = np.full((len(contracts), n_tenors), -1, dtype=int)
    for row, observation in enumerate(contracts.index):
        live = eligible_positions[
            roll_dates[eligible_positions] >= np.datetime64(observation)
        ]
        live = live[depth - 1 : depth - 1 + n_tenors]
        occupants[row, : len(live)] = live
    return occupants


def values_from_occupants(values: np.ndarray, occupants: np.ndarray) -> np.ndarray:
    """Select row-aligned values without promoting missing column values."""
    selected = np.full(occupants.shape, np.nan, dtype=float)
    rows, tenors = np.nonzero(occupants >= 0)
    selected[rows, tenors] = values[rows, occupants[rows, tenors]]
    return selected
