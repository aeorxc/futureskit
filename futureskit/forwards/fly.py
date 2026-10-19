import datetime
from calendar import month_abbr

import pandas as pd
from futureskit.forwards.util import convert_columns_to_date

fly_combos = [
    [1, 2, 3],
    [2, 3, 4],
    [3, 4, 5],
    [4, 5, 6],
    [5, 6, 7],
    [6, 7, 8],
    [7, 8, 9],
    [8, 9, 10],
    [9, 10, 11],
    [10, 11, 12],
    [11, 12, 1],
    [12, 1, 2],
]


def fly(contracts, m1, m2, m3, col_format=None):
    """
    Given a dataframe of daily values for monthly contracts (eg Brent Jan 15, Brent Feb 15, Brent Mar 15)
    with columns headings as '2020-01-01', '2020-02-01'
    Return a dataframe of flys  (eg m1 = 1, m2 = 2, m3 = 3 gives Jan/Feb/Mar fly)
    """
    contracts = convert_columns_to_date(contracts)

    cf = [x for x in contracts if x.month == m1]
    dfs = []
    legmap = {}
    for c1 in cf:
        year1, year2, year3 = c1.year, c1.year, c1.year
        # year rollover
        if m2 < m1:  # eg dec/jan/feb, make jan y+1
            year2 = year2 + 1
        if m3 < m1:
            year3 = year3 + 1
        c2 = [x for x in contracts if x.month == m2 and x.year == year2]
        c3 = [x for x in contracts if x.month == m3 and x.year == year3]
        if len(c2) == 1 and len(c3) == 1:
            c2, c3 = c2[0], c3[0]
            s = contracts[c1] + contracts[c3] - (2 * contracts[c2])
            if col_format is not None:
                if col_format == "%Y":
                    s.name = year1
                if col_format == "%b%b%b %y":
                    s.name = f"{month_abbr[m1]}{month_abbr[m2]}{month_abbr[m3]} {str(year1)[-2:]}"
            else:
                s.name = f"{month_abbr[m1]}{month_abbr[m2]}{month_abbr[m3]} {year1}"
            legmap[s.name] = [c1, c2, c3]

            if hasattr(s, 'attrs'):
                s.attrs = {}

            dfs.append(s)

    if len(dfs) > 0:
        res = pd.concat(dfs, axis=1)
        res = res.dropna(how="all", axis="rows")
        res.attrs = legmap
        return res


def all_fly_spreads(contracts, col_format=None):
    dfs = []
    for flyx in fly_combos:
        df = fly(contracts, flyx[0], flyx[1], flyx[2], col_format=col_format)
        if df is not None:
            dfs.append(df)

    if len(dfs) > 0:
        res = pd.concat(dfs, axis=1)

        legmap = {}  # TODO move this to a function reduplicates
        for df in dfs:
            legmap.update(df.attrs)
        res.attrs['legmap'] = legmap

        return res

