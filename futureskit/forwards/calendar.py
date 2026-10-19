import pandas as pd
from futureskit.forwards._strips import strip_mean
from futureskit.forwards.util import (
    CAL_LEGS,
    convert_columns_to_date,
    empty_strip_frame,
    resolve_as_of,
)


def cal_contracts(
    contracts, col_format=None, *, as_of=None, expiry_dates=None, min_legs=None
):
    """
    Given a dataframe of daily values for monthly contracts (eg Brent Jan 15, Brent Feb 15, Brent Mar 15)
    with columns headings as '2020-01-01', '2020-02-01'
    Return a dataframe of cal values (eg Cal15)

    :param as_of: the date the "current year" carve-out is judged against. An
        incomplete year is still given a column when it is the ``as_of`` year,
        because a part-built front year is expected rather than a data gap.
        Defaults to today, which is the only clock read here.
    :param expiry_dates: a curated expiry per delivery, deciding which months
        are still live on each date. ``None`` infers each from its own last
        valid observation.
    :param min_legs: quoted months a row needs before it carries a value.
        ``None`` requires every month still live on that date, so a part-expired
        year prints its balance rather than going dark. ``min_legs=1`` averages
        whatever is quoted, the lenient behaviour this function used to apply
        unconditionally.
    """
    contracts = convert_columns_to_date(contracts)
    as_of_year = resolve_as_of(as_of).year
    required = CAL_LEGS if min_legs is None else min_legs
    years = sorted({x.year for x in contracts.columns})

    dfs = []
    for year in years:
        legs = contracts[[x for x in contracts.columns if x.year == year]].dropna(
            how="all", axis=1
        )
        included = len(legs.columns) >= required or (
            # sometimes the as_of year passed in has fewer than 12 columns but
            # should still be included
            year == as_of_year
            and len(legs.columns) > 0
        )
        if not included:
            continue

        s = strip_mean(legs, expiry_dates=expiry_dates, min_legs=min_legs)
        if col_format is not None:
            if col_format == "%Y":
                s.name = year
        else:
            s.name = "CAL {}".format(year)
        dfs.append(s)

    if not dfs:
        return empty_strip_frame(contracts)

    res = pd.concat(dfs, axis=1)
    # sort columns by years
    cols = list(res.columns)
    cols.sort(key=lambda s: int(s.split()[1]) if isinstance(s, str) else s)
    res = res[cols]
    return res


def cal_spreads(q, col_format=None):
    """
    Given a dataframe of cal contract values (eg CAL 2015, CAL 2020)
    with columns headings as 'CAL 2015', 'CAL 2020'
    Return a dataframe of cal spreads (eg CAL 2015-2016)
    """

    calspr = []
    for col in q.columns:
        # colcal = col.split(' ')[0]
        colcalyr = col.split(" ")[1]

        curyear = int(colcalyr)
        nextyear = curyear + 1

        colcalnextyr = "CAL %s" % (nextyear)
        if colcalnextyr in q.columns:
            r = q[col] - q[colcalnextyr]
            if col_format:
                if col_format == "%Y":
                    r.name = curyear
            else:
                r.name = "CAL {}-{}".format(curyear, nextyear)
            calspr.append(r)

    if not calspr:
        return empty_strip_frame(q)

    res = pd.concat(calspr, axis=1, sort=True)
    return res


def half_year_contracts(contracts, *, expiry_dates=None, min_legs=None):
    """
    Given a dataframe of daily values for monthly contracts (eg Brent Jan 15, Brent Feb 15, Brent Mar 15)
    with columns headings as '2020-01-01', '2020-02-01'
    Return a dataframe of half year values (eg H115)

    :param contracts:
    :param expiry_dates: a curated expiry per delivery, deciding which months
        are still live on each date. ``None`` infers each from its own last
        valid observation.
    :param min_legs: quoted months a row needs before it carries a value.
        ``None`` requires every month still live on that date.
    :return:
    """
    contracts = convert_columns_to_date(contracts)
    years = list(set([x.year for x in contracts.columns]))

    dfs = []
    for year in years:
        c1, c2, c3, c4, c5, c6 = (
            "{}-01-01".format(year),
            "{}-02-01".format(year),
            "{}-03-01".format(year),
            "{}-04-01".format(year),
            "{}-05-01".format(year),
            "{}-06-01".format(year),
        )
        if (
                c1 in contracts.columns
                and c2 in contracts.columns
                and c3 in contracts.columns
                and c4 in contracts.columns
                and c5 in contracts.columns
                and c6 in contracts.columns
        ):
            s = strip_mean(
                pd.concat(
                    [
                        contracts[c1],
                        contracts[c2],
                        contracts[c3],
                        contracts[c4],
                        contracts[c5],
                        contracts[c6],
                    ],
                    axis=1,
                ),
                expiry_dates=expiry_dates,
                min_legs=min_legs,
            )
            s.name = "H1 {}".format(year)
            dfs.append(s)
        c7, c8, c9, c10, c11, c12 = (
            "{}-07-01".format(year),
            "{}-08-01".format(year),
            "{}-09-01".format(year),
            "{}-10-01".format(year),
            "{}-11-01".format(year),
            "{}-12-01".format(year),
        )
        if (
                c7 in contracts.columns
                and c8 in contracts.columns
                and c9 in contracts.columns
                and c10 in contracts.columns
                and c11 in contracts.columns
                and c12 in contracts.columns
        ):
            s = strip_mean(
                pd.concat(
                    [
                        contracts[c7],
                        contracts[c8],
                        contracts[c9],
                        contracts[c10],
                        contracts[c11],
                        contracts[c12],
                    ],
                    axis=1,
                ),
                expiry_dates=expiry_dates,
                min_legs=min_legs,
            )
            s.name = "H2 {}".format(year)
            dfs.append(s)
        # Winter
        c1, c2, c3, c10, c11, c12 = (
            "{}-01-01".format(year + 1),
            "{}-02-01".format(year + 1),
            "{}-03-01".format(year + 1),
            "{}-10-01".format(year),
            "{}-11-01".format(year),
            "{}-12-01".format(year),
        )
        if (
                c1 in contracts.columns
                and c2 in contracts.columns
                and c3 in contracts.columns
                and c10 in contracts.columns
                and c11 in contracts.columns
                and c12 in contracts.columns
        ):
            s = strip_mean(
                pd.concat(
                    [
                        contracts[c1],
                        contracts[c2],
                        contracts[c3],
                        contracts[c10],
                        contracts[c11],
                        contracts[c12],
                    ],
                    axis=1,
                ),
                expiry_dates=expiry_dates,
                min_legs=min_legs,
            )
            s.name = "Winter {}".format(year)
            dfs.append(s)
        # Summer
        c4, c5, c6, c7, c8, c9 = (
            "{}-04-01".format(year),
            "{}-05-01".format(year),
            "{}-06-01".format(year),
            "{}-07-01".format(year),
            "{}-08-01".format(year),
            "{}-09-01".format(year),
        )
        if (
                c4 in contracts.columns
                and c5 in contracts.columns
                and c6 in contracts.columns
                and c7 in contracts.columns
                and c8 in contracts.columns
                and c9 in contracts.columns
        ):
            s = strip_mean(
                pd.concat(
                    [
                        contracts[c4],
                        contracts[c5],
                        contracts[c6],
                        contracts[c7],
                        contracts[c8],
                        contracts[c9],
                    ],
                    axis=1,
                ),
                expiry_dates=expiry_dates,
                min_legs=min_legs,
            )
            s.name = "Summer {}".format(year)
            dfs.append(s)

    if not dfs:
        return empty_strip_frame(contracts)

    res = pd.concat(dfs, axis=1, sort=True)
    # sort columns by years
    cols = list(res.columns)
    cols.sort(key=lambda s: s.split()[1])
    res = res[cols]
    return res


def half_year_spreads(q):
    """
    Given a dataframe of half year values (eg Brent H115, Brent H215, Brent H116)
    with columns headings as 'H1 2015', 'H2 2015'
    Return a dataframe of half year spreads (eg H1-H2 15, H2-H1 15)

    """

    half_year_spread = []
    for col in q.columns:
        colhx = col.split(" ")[0]
        colhxyr = col.split(" ")[1]
        if colhx == "H2":
            colhxyr = int(colhxyr) + 1
        colqy = f"H2 {colhxyr}" if colhx == "H1" else f"H1 {colhxyr}"
        if colqy in q.columns:
            r = q[col] - q[colqy]
            r.name = "{}{} {}".format(colhx, colqy.split(" ")[0], col.split(" ")[1])
            half_year_spread.append(r)

    for col in q.columns:
        colhx = col.split(" ")[0]
        colhxyr = col.split(" ")[1]
        if colhx == "Summer":
            colqy = f"Winter {colhxyr}"
            if colqy in q.columns:
                r = q[col] - q[colqy]
                r.name = "{}{} {}".format(colhx, colqy.split(" ")[0], col.split(" ")[1])
                half_year_spread.append(r)
        if colhx == "Winter":
            colqy = f"Summer {int(colhxyr) + 1}"
            if colqy in q.columns:
                r = q[col] - q[colqy]
                r.name = "{}{} {}".format(colhx, colqy.split(" ")[0], col.split(" ")[1])
                half_year_spread.append(r)

    if not half_year_spread:
        return empty_strip_frame(q)

    res = pd.concat(half_year_spread, axis=1, sort=True)
    return res
