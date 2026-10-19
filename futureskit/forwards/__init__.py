"""
Utility for forward contracts
"""
import re
from calendar import month_abbr, monthrange
import numpy as np
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import List

from futureskit.forwards.calendar import cal_contracts, cal_spreads, half_year_contracts, half_year_spreads
from futureskit.forwards.structure import (
    forward_rolling_structure,
    generate_structure_series,
    rolling_structure,
)
from futureskit.forwards.continuous import (
    generate_multiple_continuous_series,
    generate_series,
)
from futureskit.forwards.fly import fly as _fly, all_fly_spreads, fly_combos
from futureskit.forwards.quarterly import quarterly_contracts, all_quarterly_rolls, time_spreads_quarterly, \
    fly_quarterly, all_quarterly_flys
from futureskit.forwards.spreads import time_spreads_monthly, all_monthly_spreads, monthly_spread_combos_extended
from futureskit.forwards._occupancy import (
    BEYOND_SAMPLE,
    infer_expiry_dates,
    merge_expiry_dates,
)
from futureskit.forwards.util import convert_columns_to_date, empty_strip_frame, month_abbr_inv, resolve_as_of, _find_year
from futureskit.forwards.schema import validate_contract_matrix, validate_expiry_dates
from futureskit.forwards.rollspec import Adjustment, ExpiryOffset, RollRule, RollSpec
from futureskit.forwards.constant_maturity import (
    ConstantMaturityGrid,
    constant_maturity_grid,
)

__all__ = [
    "Adjustment",
    "ExpiryOffset",
    "RollRule",
    "RollSpec",
    "ConstantMaturityGrid",
    "constant_maturity_grid",
    "generate_multiple_continuous_series",
    "generate_series",
    "validate_contract_matrix",
    "validate_expiry_dates",
    "BEYOND_SAMPLE",
    "infer_expiry_dates",
    "merge_expiry_dates",
    "cal_contracts",
    "cal_spreads",
    "half_year_contracts",
    "half_year_spreads",
    "generate_structure_series",
    "rolling_structure",
    "forward_rolling_structure",
    "all_fly_spreads",
    "fly_combos",
    "quarterly_contracts",
    "all_quarterly_rolls",
    "time_spreads_quarterly",
    "fly_quarterly",
    "all_quarterly_flys",
    "time_spreads_monthly",
    "all_monthly_spreads",
    "monthly_spread_combos_extended",
    "convert_columns_to_date",
    "month_abbr_inv",
    "time_spreads",
    "all_spread_combinations",
    "replace_last_month_with_nan",
    "spread_combination_quarter",
    "spread_combination_fly",
    "spread_combination_month",
    "spread_combination",
    "filter_columns_by_date",
    "recent_structure",
    "recent_spreads",
]


def time_spreads(contracts, m1, m2):
    """
    Given a dataframe of daily values for monthly contracts (eg Brent Jan 15, Brent Feb 15, Brent Mar 15)
    with columns headings as '2020-01-01', '2020-02-01'
    Return a dataframe of time spreads  (eg m1 = 12, m2 = 12 gives Dec-Dec spread)
    """
    if isinstance(m1, int) and isinstance(m2, int):
        return time_spreads_monthly(contracts, m1, m2, col_format="%Y")

    if m1.lower().startswith("q") and m2.lower().startswith("q"):
        return time_spreads_quarterly(contracts, m1, m2)


def all_spread_combinations(contracts, *, as_of=None, expiry_dates=None, min_legs=None):
    """Build every strip, spread and fly this module knows from one frame.

    :param as_of: passed to :func:`cal_contracts` for its current-year rule.
    :param expiry_dates: passed to the calendar, quarterly and half-year
        builders, deciding which legs are live on each date.
    :param min_legs: passed to the same three builders.
    """
    strip_policy = {"expiry_dates": expiry_dates, "min_legs": min_legs}
    output = {}
    output["Calendar"] = cal_contracts(contracts, as_of=as_of, **strip_policy)
    output["Calendar Spread"] = cal_spreads(output["Calendar"])
    output["Quarterly"] = quarterly_contracts(contracts, **strip_policy)
    output["Half Year"] = half_year_contracts(contracts, **strip_policy)

    q = output["Quarterly"]
    for qx in ["Q1", "Q2", "Q3", "Q4"]:
        output[qx] = q[[x for x in q if qx in x]]
    output["Quarterly Spread"] = all_quarterly_rolls(q)
    q = output["Quarterly Spread"]
    for qx in ["Q1Q2", "Q2Q3", "Q3Q4", "Q4Q1"]:
        output[qx] = q[[x for x in q if qx in x]]

    output["Half Year Spread"] = half_year_spreads(output["Half Year"])

    contracts = convert_columns_to_date(contracts)
    for month in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]:
        output[month] = contracts[[x for x in contracts.columns if x.month == month]]

    for spread in monthly_spread_combos_extended:
        tag = "%s%s" % (month_abbr[spread[0]], month_abbr[spread[1]])
        output[tag] = time_spreads(contracts, spread[0], spread[1])

    for flyx in fly_combos:
        tag = "%s%s%s" % (month_abbr[flyx[0]], month_abbr[flyx[1]], month_abbr[flyx[2]])
        output[tag] = _fly(contracts, flyx[0], flyx[1], flyx[2])

    return output


def replace_last_month_with_nan(contracts, as_of=None):
    """Drop terminal months only from columns that stopped before ``as_of``."""
    contracts = contracts.copy()
    if isinstance(contracts, pd.DataFrame):
        frame_dropped_na = contracts.dropna(how="all")
        if frame_dropped_na.empty:
            return contracts
        if as_of is None:
            as_of = frame_dropped_na.index.max()
        return contracts.apply(replace_last_month_with_nan, axis=0, as_of=as_of)

    series_dropped_na = contracts.dropna()
    if series_dropped_na.empty:
        return contracts
    last_valid = series_dropped_na.index.max()
    if as_of is None or last_valid >= pd.Timestamp(as_of):
        return contracts
    last_month = pd.to_datetime(f"{last_valid.year}-{last_valid.month}-01")
    _, last_day = monthrange(last_month.year, last_month.month)
    last_valid_month_end = pd.to_datetime(f"{last_month.year}-{last_month.month}-{last_day}")
    contracts[last_month:last_valid_month_end] = np.nan

    return contracts


def spread_combination_quarter(contracts, combination_type, verbose_columns=True, exclude_price_month=False,
                               col_format=None):

    if combination_type.startswith("q"):
        m = re.search(r"q\dq\dq\d", combination_type)
        if m:
            if exclude_price_month:
                contracts = replace_last_month_with_nan(contracts)
            q_contracts = quarterly_contracts(contracts)
            q_spreads = fly_quarterly(
                q_contracts,
                x=int(combination_type[1]),
                y=int(combination_type[3]),
                z=int(combination_type[5]),
            )
            if not verbose_columns:
                colmap = _find_year(q_spreads)
                q_spreads = q_spreads.rename(
                    columns={x: colmap[x] for x in q_spreads.columns}
                )
            return q_spreads
        m = re.search(r"q\dq\d", combination_type)
        if m:
            if exclude_price_month:
                contracts = replace_last_month_with_nan(contracts)
            q_spreads = time_spreads_quarterly(
                contracts, combination_type[0:2], combination_type[2:4]
            )
            if verbose_columns:
                colmap = _find_year(q_spreads)
                q_spreads = q_spreads.rename(
                    columns={
                        x: "%s %s" % (combination_type.upper(), colmap[x])
                        for x in q_spreads.columns
                    }
                )
            return q_spreads

        m = re.search(r"q\d", combination_type)
        if m:
            q_contracts = quarterly_contracts(contracts)
            q_contracts = q_contracts[
                [
                    x
                    for x in q_contracts.columns
                    if x.startswith(combination_type.upper())
                ]
            ]
            if not verbose_columns:
                colmap = _find_year(q_contracts)
                q_contracts = q_contracts.rename(
                    columns={x: colmap[x] for x in q_contracts.columns}
                )
            return q_contracts


def spread_combination_fly(contracts, combination_type, verbose_columns=True, exclude_price_month=False,
                           col_format=None):
    months = [x.lower() for x in month_abbr]
    if exclude_price_month:
        contracts = replace_last_month_with_nan(contracts)
    m1, m2, m3 = combination_type[0:3], combination_type[3:6], combination_type[6:9]
    if m1 in months and m2 in months and m3 in months:
        c = _fly(
            contracts, month_abbr_inv[m1], month_abbr_inv[m2], month_abbr_inv[m3]
        )
        # if verbose_columns:
        #     c = c.rename(
        #         columns={
        #             x: "%s%s%s %s" % (m1.title(), m2.title(), m3.title(), x)
        #             for x in c.columns
        #         }
        #     )
        return c


def spread_combination_month(contracts, combination_type, verbose_columns=True, exclude_price_month=False,
                             col_format=None):
    months = [x.lower() for x in month_abbr]
    m1, m2 = combination_type[0:3], combination_type[3:6]
    if m1 in months and m2 in months:
        if exclude_price_month:
            contracts = replace_last_month_with_nan(contracts)
        c = time_spreads(contracts, month_abbr_inv[m1], month_abbr_inv[m2])
        if verbose_columns:
            c = c.rename(
                columns={
                    x: "%s%s %s" % (m1.title(), m2.title(), x) for x in c.columns
                }
            )
        return c


def spread_combination(contracts, combination_type, verbose_columns=True, exclude_price_month=False, col_format=None,
                       *, as_of=None, expiry_dates=None, min_legs=None):
    """
    Convenience method to access functionality in forwards using a combination_type keyword
    :param contracts:
    :param combination_type:
    :param as_of: passed to :func:`cal_contracts` for its current-year rule.
    :param expiry_dates: passed to the calendar, quarterly and half-year
        builders, deciding which legs are live on each date.
    :param min_legs: passed to the same three builders.
    :return:
    """
    strip_policy = {"expiry_dates": expiry_dates, "min_legs": min_legs}
    combination_type = combination_type.lower().replace(" ", "")
    contracts = contracts.dropna(how="all", axis="rows")

    if combination_type == "calendar":
        c_contracts = cal_contracts(contracts, col_format="%Y", as_of=as_of, **strip_policy)
        return c_contracts
    if combination_type == "calendarspread":
        c_contracts = cal_spreads(
            cal_contracts(contracts, as_of=as_of, **strip_policy), col_format=col_format
        )
        return c_contracts
    if combination_type == "halfyear":
        c_contracts = half_year_contracts(contracts, **strip_policy)
        return c_contracts
    if combination_type == "halfyearspread":
        c_contracts = half_year_spreads(half_year_contracts(contracts, **strip_policy))
        return c_contracts

    if combination_type.startswith("monthly"):
        if col_format is None:
            col_format = "%b%b %y"
        return all_monthly_spreads(contracts, col_format=col_format)

    if combination_type.startswith("fly"):
        if col_format is None:
            col_format = "%b%b%b %y"
        return all_fly_spreads(contracts, col_format=col_format)

    if combination_type.startswith("quarterlyroll"):
        if col_format is None:
            col_format = "%q%q %y"
        return all_quarterly_rolls(
            quarterly_contracts(contracts, **strip_policy), col_format=col_format
        )

    if combination_type.startswith("quarterlyfly"):
        if col_format is None:
            col_format = "%q%q%q %y"
        return all_quarterly_flys(
            quarterly_contracts(contracts, **strip_policy), col_format=col_format
        )

    if combination_type.startswith("quarterly"):
        if col_format is None:
            col_format = "%q %y"
        return quarterly_contracts(contracts, col_format=col_format, **strip_policy)

    if combination_type.startswith("q"):
        return spread_combination_quarter(contracts, combination_type=combination_type, verbose_columns=verbose_columns,
                                          exclude_price_month=exclude_price_month, col_format=col_format)

    # handle monthly, spread and fly inputs
    contracts = convert_columns_to_date(contracts)
    months = [x.lower() for x in month_abbr]
    if len(combination_type) == 3 and combination_type in months:
        c = contracts[
            [x for x in contracts if x.month == month_abbr_inv[combination_type]]
        ]
        if verbose_columns:
            c = c.rename(columns={x: x.strftime("%b %Y") for x in c.columns})
        else:
            c = c.rename(columns={x: x.year for x in c.columns})
        return c
    if len(combination_type) == 6:  # spread
        return spread_combination_month(contracts, combination_type, verbose_columns=verbose_columns,
                                        exclude_price_month=exclude_price_month, col_format=col_format)
    if len(combination_type) == 9:  # fly
        return spread_combination_fly(contracts, combination_type, verbose_columns=verbose_columns,
                                      exclude_price_month=exclude_price_month, col_format=col_format)


def filter_columns_by_date(contract_data, start_date, end_date):
    if isinstance(start_date, pd.Timestamp):
        start_date = start_date.date()
    if isinstance(end_date, pd.Timestamp):
        end_date = end_date.date()
    # return [col for col in contract_data.columns if start_date <= col.to_pydatetime().date() <= end_date]
    return [col for col in contract_data.columns
            if start_date <= (col.date() if isinstance(col, pd.Timestamp) else col) <= end_date]


def recent_structure(contracts: pd.DataFrame, structure_combo: List[List[int]] = [[1, 2], [1, 3], [1, 6], [1, 12]],
                     roll_days: int = 0) -> pd.DataFrame:
    """
    Given a list of contracts, calculate structure.

    :param contracts: DataFrame with individual contracts as columns.
    :param structure_combo: List of lists where each sublist represents a structure to calculate.
    :param roll_days: Number of days before the expiry date to roll to the next contract.
    :return: DataFrame representing the calculated structure for each structure combo.
    """
    contracts = convert_columns_to_date(contracts)
    dfs = [
        generate_structure_series(contracts, mx=mx, my=my, roll_days=roll_days)
        for mx, my in structure_combo
    ]
    df = pd.concat(dfs, axis=1)
    df = df.dropna(how="all", axis="rows")

    return df


def recent_spreads(contracts: pd.DataFrame, combination_type: str, *, as_of=None, **kwargs):
    """Given a list of contracts, filter the contracts to the list of most recent relevant contracts

    :param as_of: the date the relevance window is centred on, defaulting to
        today. Supplying it makes the result a function of its arguments alone:
        the monthly window is ``as_of`` minus three months to plus six, and the
        quarterly window minus five to plus sixteen, whatever day this runs on.
    """
    if contracts is None:
        return None

    if combination_type == 'structure':
        return recent_structure(contracts, **kwargs)

    contracts = convert_columns_to_date(contracts)
    current_date = resolve_as_of(as_of).date()  # Convert to datetime.date
    start_date = current_date - relativedelta(months=3)  # Approximating a month as 30 days
    end_date = current_date + relativedelta(months=6)  # Approximating a month as 30 days
    filtered_columns = filter_columns_by_date(contracts, start_date, end_date)

    start_date_qtr = current_date - relativedelta(months=5)
    end_date_qtr = current_date + relativedelta(months=16)
    filtered_columns_qtr = filter_columns_by_date(contracts, start_date_qtr, end_date_qtr)

    if combination_type == "contracts":
        month_df = contracts[filtered_columns]
        month_df.columns = [f"{col.strftime('%b%y').lower()}" for col in month_df.columns]
        return month_df
    elif combination_type in ['monthly']:
        spread_df = spread_combination(contracts[filtered_columns], combination_type="monthly",
                                       col_format="%b%b %y")

        return spread_df

    elif combination_type in ['quarterly']:
        spread_df = spread_combination(contracts=contracts[filtered_columns_qtr],
                                       combination_type="quarterly",
                                       col_format="%q %y")

        return spread_df

    elif combination_type in ['quarterly roll']:
        spread_df = spread_combination(contracts=contracts[filtered_columns_qtr],
                                       combination_type="quarterly roll",
                                       col_format="%q%q %y")

        return spread_df
    elif combination_type in ['quarterly fly']:
        spread_df = spread_combination(contracts=contracts[filtered_columns_qtr],
                                       combination_type="quarterly fly",
                                       col_format="%q%q%q %y")

        return spread_df

    elif combination_type in ['fly']:
        spread_df = spread_combination(contracts=contracts[filtered_columns], combination_type="fly",
                                       col_format="%b%b%b %y")
        return spread_df

# if __name__ == "__main__":
# from pylim import lim
#
#     df = lim.series(["CL_2023Z", "CL_2024F"])
#     spread_combination(df, "DecJan")
