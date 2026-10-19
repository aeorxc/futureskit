import pandas as pd
from futureskit.forwards._strips import strip_mean
from futureskit.forwards.util import (
    convert_columns_to_date,
    empty_strip_frame,
    _find_year,
)


def time_spreads_quarterly(contracts, m1, m2):
    """
    Given a dataframe of daily values for monthly contracts (eg Brent Jan 15, Brent Feb 15, Brent Mar 15)
    with columns headings as '2020-01-01', '2020-02-01'
    Return a dataframe of time spreads  (eg m1 = Q1, m2 = Q2 gives Q1-Q2 spread)
    """
    contracts = convert_columns_to_date(contracts)

    m1, m2 = m1.upper(), m2.upper()
    qtrcontracts = quarterly_contracts(contracts)
    qtrcontracts_years = _find_year(qtrcontracts)
    cf = [x for x in qtrcontracts if x.startswith(m1)]
    dfs = []

    for c1 in cf:
        year1, year2 = qtrcontracts_years[c1], qtrcontracts_years[c1]
        if int(m1[-1]) >= int(
                m2[-1]
        ):  # eg Q1-Q1 or Q4-Q1, then do Q419 - Q120 (year ahead)
            year2 = year1 + 1
        c2 = [
            x
            for x in qtrcontracts
            if x.startswith(m2) and qtrcontracts_years[x] == year2
        ]
        if len(c2) == 1:
            c2 = c2[0]
            s = qtrcontracts[c1] - qtrcontracts[c2]
            s.name = year1
            dfs.append(s)

    if not dfs:
        return empty_strip_frame(contracts)

    res = pd.concat(dfs, axis=1)
    res = res.dropna(how="all", axis="rows")
    return res


def calculate_quarter(
    contracts, year, months, col_format=None, *, expiry_dates=None, min_legs=None
):
    """Average one quarter's three delivery months.

    :param expiry_dates: a curated expiry per delivery, deciding which months
        are still live on each date. ``None`` infers each from its own last
        valid observation.
    :param min_legs: quoted months a row needs before it carries a value.
        ``None`` requires every month still live on that date.
    """
    month_cols = [f"{year}-{month:02d}-01" for month in months]
    if all(col in contracts.columns for col in month_cols):
        s = strip_mean(
            contracts[month_cols], expiry_dates=expiry_dates, min_legs=min_legs
        )
        if col_format is not None:
            if col_format == "%q %y":
                s.name = f"Q{months[0]//3 + 1} {str(year)[-2:]}"
        else:
            s.name = f"Q{months[0]//3 + 1} {year}"
        return s


def quarterly_contracts(
    contracts, col_format=None, *, expiry_dates=None, min_legs=None
):
    """
    Given a dataframe of daily values for monthly contracts (eg Brent Jan 15, Brent Feb 15, Brent Mar 15)
    with columns headings as '2020-01-01', '2020-02-01'
    Return a dataframe of quarterly values (eg Q115)

    :param expiry_dates: a curated expiry per delivery, deciding which months
        are still live on each date. ``None`` infers each from its own last
        valid observation.
    :param min_legs: quoted months a row needs before it carries a value.
        ``None`` requires every month still live on that date.
    """


    contracts = convert_columns_to_date(contracts)
    years = list(set([x.year for x in contracts.columns]))

    dfs = []
    for year in years:
        for quarter in range(4):
            months = range(quarter * 3 + 1, quarter * 3 + 4)
            s = calculate_quarter(
                contracts,
                year,
                months,
                col_format=col_format,
                expiry_dates=expiry_dates,
                min_legs=min_legs,
            )
            if s is not None:
                dfs.append(s)

    if not dfs:
        return empty_strip_frame(contracts)

    res = pd.concat(dfs, axis=1, sort=True)
    # sort columns by years
    cols = list(res.columns)
    cols.sort(key=lambda s: s.split()[1])
    res = res[cols]
    return res


def all_quarterly_rolls(q, col_format=None):
    """
    Given a dataframe of quarterly contract values (eg Brent Q115, Brent Q215, Brent Q315)
    with columns headings as 'Q1 2015', 'Q2 2015'
    Return a dataframe of quarterly spreads (eg Q1-Q2 15)
    Does Q1-Q2, Q2-Q3, Q3-Q4, Q4-Q1
    """
    sprmap = {
        "Q1": "Q2 {}",
        "Q2": "Q3 {}",
        "Q3": "Q4 {}",
        "Q4": "Q1 {}",
    }

    qtrspr = []
    for col in q.columns:
        colqx = col.split(" ")[0]
        colqxyr = col.split(" ")[1]
        if colqx == "Q4":
            colqxyr = int(colqxyr) + 1
        colqy = sprmap.get(colqx).format(colqxyr)
        if colqy in q.columns:
            r = q[col] - q[colqy]
            if col_format is not None:
                if col_format == "%q%q %y":
                    r.name = "{}{} {}".format(colqx, colqy.split(" ")[0], col.split(" ")[1][-2:])
            else:
                r.name = "{}{} {}".format(colqx, colqy.split(" ")[0], col.split(" ")[1])
            qtrspr.append(r)

    if not qtrspr:
        return empty_strip_frame(q)

    res = pd.concat(qtrspr, axis=1, sort=True)
    return res


def fly_quarterly(contracts, x, y, z, col_format=None):
    """
    Given a dataframe of quarterly contract values (eg Brent Q115, Brent Q215, Brent Q315)
    with columns headings as 'Q1 2015', 'Q2 2015'
    Return a dataframe of flys  (eg x = q1 y = q2 z = q3 gives Q1/Q2/Q3 fly)
    """
    contracts = convert_columns_to_date(contracts)

    dfs = []
    cf = [n for n in contracts if "Q%s" % x in n]
    for c1 in cf:
        year1, year2, year3 = int(c1[-4:]), int(c1[-4:]), int(c1[-4:])
        # year rollover

        if x == 4 and y == 1:  # 412 or 413
            year2 = year2 + 1
            year3 = year3 + 1
        if (x == 2 and y == 3 and z == 1) or (x == 2 and y == 3 and z == 1):
            year3 = year3 + 1
        if x == 3 and y == 4:  # 341 or 342
            year3 = year3 + 1

        c2 = [n for n in contracts if "Q%d" % y in n and str(year2) in n]
        c3 = [n for n in contracts if "Q%d" % z in n and str(year3) in n]
        if len(c2) == 1 and len(c3) == 1:
            c2, c3 = c2[0], c3[0]
            s = contracts[c1] + contracts[c3] - (2 * contracts[c2])
            if col_format is not None:
                if col_format == "%q%q%q %y":
                    s.name = "Q%dQ%dQ%d %s" % (x, y, z, str(year1)[-2:])
            else:
                s.name = "Q%dQ%dQ%d %d" % (x, y, z, year1)
            dfs.append(s)

    if not dfs:
        return empty_strip_frame(contracts)

    res = pd.concat(dfs, axis=1)
    res = res.dropna(how="all", axis="rows")
    return res


def all_quarterly_flys(q, col_format=None):
    """
    Given a dataframe of quarterly contract values (eg Brent Q115, Brent Q215, Brent Q315)
    with columns headings as 'Q1 2015', 'Q2 2015'
    Return a dataframe of quarterly flys (eg Q1Q2Q3)
    Does Q1Q2Q3, Q2Q3Q4, Q3Q4Q1, Q4Q1Q2
    """
    flycombos = ((1, 2, 3), (2, 3, 4), (3, 4, 1), (4, 1, 2))

    dfs = []
    for flycombo in flycombos:
        s = fly_quarterly(contracts=q, x=flycombo[0], y=flycombo[1], z=flycombo[2], col_format=col_format)
        dfs.append(s)

    dfs = [df for df in dfs if not df.empty]
    if not dfs:
        return empty_strip_frame(q)

    res = pd.concat(dfs, axis=1, sort=True)
    return res
