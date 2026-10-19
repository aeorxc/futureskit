from calendar import month_abbr

import pandas as pd
from futureskit.forwards.util import convert_columns_to_date


monthly_spread_combos = [
        [1, 2],
        [2, 3],
        [3, 4],
        [4, 5],
        [5, 6],
        [6, 7],
        [7, 8],
        [8, 9],
        [9, 10],
        [10, 11],
        [11, 12],
        [12, 1],

    ]
monthly_spread_combos_extended = [
        [1, 2],
        [2, 3],
        [3, 4],
        [4, 5],
        [5, 6],
        [6, 7],
        [7, 8],
        [8, 9],
        [9, 10],
        [10, 11],
        [11, 12],
        [12, 1],
        [6, 6],
        [6, 12],
        [12, 12],
        [10, 12],
        [4, 9],
        [10, 3],

    ]


def time_spreads_monthly(contracts, m1, m2, col_format=None):
    """
    Given a dataframe of daily values for monthly contracts (eg Brent Jan 15, Brent Feb 15, Brent Mar 15)
    with columns headings as '2020-01-01', '2020-02-01'
    Return a dataframe of time spreads  (eg m1 = 12, m2 = 12 gives Dec-Dec spread)
    """

    contracts = convert_columns_to_date(contracts)

    cf = [x for x in contracts if x.month == m1]
    dfs = []
    legmap = {}

    for c1 in cf:
        year1, year2 = c1.year, c1.year
        if m2 <= m1:
            year2 = year1 + 1
        c2 = [x for x in contracts if x.month == m2 and x.year == year2]
        if len(c2) == 1:
            c2 = c2[0]
            s = contracts[c1] - contracts[c2]
            if col_format:
                if col_format == "%Y":
                    s.name = year1
                if col_format == "%b%b %Y":
                    s.name = f"{month_abbr[m1]}{month_abbr[m2]} {year1}"
                if col_format == "%b%b %y":
                    s.name = f"{month_abbr[m1]}{month_abbr[m2]} {str(year1)[-2:]}"
            else:
                s.name = f"{month_abbr[m1]}{month_abbr[m2]} {year1}"
            legmap[s.name] = [c1, c2]

            if hasattr(s, 'attrs'):
                s.attrs = {}
            dfs.append(s)

    if len(dfs) > 0:


        res = pd.concat(dfs, axis=1)
        res = res.dropna(how="all", axis="rows")
        res.attrs["legmap"] = legmap
        return res


def all_monthly_spreads(contracts, col_format=None):
    dfs = []
    for spread in monthly_spread_combos:
        df = time_spreads_monthly(contracts, spread[0], spread[1], col_format=col_format)
        if df is not None:
            dfs.append(df)

    res = pd.concat(dfs, axis=1)
    legmap = {}
    for df in dfs:
        legmap.update(df.attrs["legmap"])
    res.attrs['legmap'] = legmap

    return res


def all_monthly_spreads_extended(contracts, col_format=None):
    """
    Like `all_monthly_spreads`, but includes a broader set of month pairs.

    This includes:
    - standard adjacent-month spreads (JanFeb, ..., DecJan)
    - a handful of common seasonal / 1y spreads (e.g. JunJun, DecDec, OctMar)
    """
    dfs = []
    for spread in monthly_spread_combos_extended:
        df = time_spreads_monthly(contracts, spread[0], spread[1], col_format=col_format)
        if df is not None:
            dfs.append(df)

    if not dfs:
        return None

    res = pd.concat(dfs, axis=1, sort=True)
    legmap = {}
    for df in dfs:
        legmap.update(df.attrs["legmap"])
    res.attrs["legmap"] = legmap
    return res
