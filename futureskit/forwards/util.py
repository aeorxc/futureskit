import datetime
import re
import warnings
from calendar import month_abbr

import numpy as np
import pandas as pd

from futureskit.notation import MONTH_CODES

month_abbr_inv = {
    month.lower(): index for index, month in enumerate(month_abbr) if month
}


#: Legs in a full calendar strip, used to decide which years get a column.
CAL_LEGS = 12


def resolve_as_of(as_of=None) -> pd.Timestamp:
    """Normalise an ``as_of`` argument to a midnight ``Timestamp``.

    ``None`` means today. This is the only place in the strip builders that
    reads the wall clock, so a caller supplying ``as_of`` gets a function of
    its arguments alone: the same frame and the same ``as_of`` always produce
    the same frame, whatever day the code runs on.
    """
    if as_of is None:
        return pd.Timestamp.today().normalize()
    return pd.Timestamp(as_of).normalize()


def empty_strip_frame(source) -> pd.DataFrame:
    """The empty result every strip and spread builder returns.

    One convention, so a caller can index the result without first testing it
    for ``None``: a DataFrame with no columns, carrying the input's index so
    the result still aligns with the frame it was derived from.
    """
    index = getattr(source, "index", None)
    return pd.DataFrame(index=index if index is not None else None)


# TODO: Unify convert_contract_to_date with FuturesNotation in a future change.
def convert_contract_to_date(contract):
    """
    Given a string like FB_2020J return 2020-01-01
    :param contract:
    :return:
    """
    c = re.findall(r"\d\d\d\d\w", contract)
    if len(c) > 0:
        c = c[0]
    d = "%s-%s-1" % (c[:4], MONTH_CODES.get(c[-1], 0))
    return d


def convert_columns_to_date(contracts: pd.DataFrame) -> pd.DataFrame:
    remap = {}
    columns = []
    values = []
    for col in contracts.columns:
        if isinstance(col, pd.Timestamp):
            continue
        try:
            if isinstance(col, datetime.date):
                value = col
            else:
                value = convert_contract_to_date(col)
            columns.append(col)
            values.append(value)
        except IndexError as _:
            pass
        except TypeError as _:
            pass
    try:
        remap.update(zip(columns, pd.to_datetime(values)))
    except (TypeError, ValueError):
        for col, value in zip(columns, values):
            remap[col] = pd.to_datetime(value)
    contracts = contracts.rename(columns=remap)
    return contracts


def _find_year(df):
    res = {}
    for colname in df:
        colregex = re.findall(r"\d\d\d\d", str(colname))
        colyear = None
        if len(colregex) >= 1:
            colyear = int(colregex[0])

        if colyear:
            res[colname] = colyear
        else:
            res[colname] = colname

    return res


def determine_roll_date(df, expiry_date, roll_days, trading_day_index=None):
    """Anchor at the last printing day on/before expiry, then step back.

    Days are compared as dates, so every print on the expiry day is eligible
    whatever its time of day. Printing days are the observed trading days,
    extended past the end of the sample with business days (Monday to Friday)
    up to the expiry. When the prints that follow match that calendar, a
    sample that stops before the expiry rolls on the same day as one that
    contains it, so history is not restated once the expiry enters the sample.
    The extension knows no exchange holidays: a weekday without a print inside
    the window projects the roll one day late, and the roll moves earlier
    once the expiry is observed. :data:`BEYOND_SAMPLE` never rolls, whatever
    ``roll_days`` is. Insufficient history returns a timestamp before the
    sample so the contract is never selected.
    """
    from futureskit.forwards._occupancy import BEYOND_SAMPLE

    if trading_day_index is None:
        trading_day_index = df.dropna(how="all", axis="rows").index
    expiry = pd.Timestamp(expiry_date)
    if trading_day_index.empty or expiry >= BEYOND_SAMPLE:
        return expiry_date
    expiry_day = expiry.normalize()
    observed_days = pd.DatetimeIndex(trading_day_index).normalize()
    sample_end = observed_days[-1]
    if expiry_day > sample_end:
        # Business days after the sample, up to and including the expiry day.
        one_day = pd.Timedelta(days=1)
        future_days = int(
            np.busday_count(
                (sample_end + one_day).date(), (expiry_day + one_day).date()
            )
        )
        if roll_days < future_days:
            return pd.Timestamp(
                np.busday_offset(expiry_day.date(), -roll_days, roll="backward")
            )
        roll_days -= future_days
    eligible = trading_day_index[observed_days <= expiry_day]
    if eligible.empty:
        return expiry_date
    new_idx_position = len(eligible) - 1 - roll_days
    if new_idx_position >= 0:
        return eligible[new_idx_position]
    # The requested roll precedes every observed trading day, so the contract
    # must not occupy a tenor on the first observation.
    return trading_day_index[0] - pd.Timedelta(1, unit="ns")


def extract_expiry_dates_from_contracts(contracts):
    """Deprecated alias for :func:`futureskit.forwards.infer_expiry_dates`.

    .. deprecated:: 1.0.0
       Call :func:`futureskit.forwards.infer_expiry_dates` directly.

    It delegates so that the package holds exactly one inference rule. Its own
    rule was a bare last-observation read with no gap guard and no delivery
    month cap, and its result validates as a complete expiry map, so a caller
    could hand it straight back to a continuous-series call and reproduce every
    inference bug the canonical engine fixes — a whole windowed board declared
    expired on its final row, or a delivery held live by post-expiry prints
    past the end of its delivery month.

    Two behaviours change with the delegation, both of them the reason it was
    deprecated. Deduplication is gone: it used to omit any delivery whose last
    observation matched an earlier column's, which silently deleted far-tenor
    tails from a ladder built on it. And a column quoted through the sample now
    takes ``BEYOND_SAMPLE`` rather than the sample's end date.
    """
    from futureskit.forwards._occupancy import infer_expiry_dates

    warnings.warn(
        "extract_expiry_dates_from_contracts is deprecated and will be removed "
        "in a future release. Use futureskit.forwards.infer_expiry_dates "
        "instead; this function now delegates to it, so it no longer drops "
        "contracts that share an expiry date.",
        DeprecationWarning,
        stacklevel=2,
    )
    return infer_expiry_dates(contracts)
