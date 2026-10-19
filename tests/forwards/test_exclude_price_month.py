import numpy as np
import pandas as pd

from futureskit import forwards


def _live_contracts():
    index = pd.to_datetime(
        ["2026-07-31", "2026-08-03", "2026-08-31", "2026-09-01", "2026-09-09"]
    )
    contracts = pd.DataFrame(
        {
            pd.Timestamp("2026-08-01"): [70.0, 71.0, 72.0, np.nan, np.nan],
            pd.Timestamp("2026-10-01"): [73.0, 74.0, 75.0, 76.0, 77.0],
            pd.Timestamp("2026-11-01"): [74.0, 75.0, 76.0, 77.0, 78.0],
            pd.Timestamp("2026-12-01"): [76.0, 77.0, 78.0, 79.0, 80.0],
            pd.Timestamp("2027-01-01"): [77.0, 78.0, 79.0, 80.0, 81.0],
            pd.Timestamp("2027-02-01"): [79.0, 80.0, 81.0, 82.0, 83.0],
            pd.Timestamp("2027-03-01"): [80.0, 81.0, 82.0, 83.0, 84.0],
        },
        index=index,
    )
    return contracts


def test_exclude_price_month_keeps_live_monthly_structures():
    contracts = _live_contracts()

    spread = forwards.spread_combination(contracts, "octnov", exclude_price_month=True)
    fly = forwards.spread_combination(contracts, "octnovdec", exclude_price_month=True)

    assert spread["OctNov 2026"].last_valid_index() == pd.Timestamp("2026-09-09")
    assert fly["OctNovDec 2026"].last_valid_index() == pd.Timestamp("2026-09-09")


def test_exclude_price_month_keeps_live_quarter_roll():
    contracts = _live_contracts()

    quarter_roll = forwards.spread_combination(
        contracts, "q4q1", exclude_price_month=True
    )

    assert quarter_roll["Q4Q1 2026"].last_valid_index() == pd.Timestamp("2026-09-09")


def test_exclude_price_month_still_masks_expired_contract_without_mutating_input():
    contracts = _live_contracts()

    masked = forwards.replace_last_month_with_nan(contracts)

    assert contracts.loc["2026-08-31", pd.Timestamp("2026-08-01")] == 72.0
    assert masked.loc["2026-08", pd.Timestamp("2026-08-01")].isna().all()
    assert masked.loc["2026-09-09", pd.Timestamp("2026-10-01")] == 77.0
