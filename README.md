# futureskit

A Python library for parsing and working with futures contract symbols and notation.

## Overview

futureskit is two things, and nothing else:

- **Notation** - parse futures contract references (`BRN_2026F`, `BRN26F`, `BRN.n.1`) and
  format vendor symbol spellings for Refinitiv/LSEG and TradingView.
- **Forwards** - pure contract-matrix curve construction: continuous series, the
  constant-maturity tenor grid, spreads, flies, quarterly and calendar strips.

The library is pure and calendar-ignorant. Frames go in and frames come out; there is no
I/O, no network and no vendored expiry table or exchange calendar. Expiry dates always
arrive as an argument. Runtime dependencies are numpy, pandas and python-dateutil.

## Installation

```bash
pip install futureskit
```

## Development

The repository uses [uv](https://docs.astral.sh/uv/). Runtime dependencies are
package metadata in `pyproject.toml`; test and developer tools are declared in
PEP 735 dependency groups.

The published `futureskit[test]` and `futureskit[dev]` extras are retained for
consumer compatibility.

Create the developer environment and run the suite:

```bash
uv sync --group test
uv run pytest
```

The package supports Python 3.11 and newer.

## Quick Start

```python
import pandas as pd

from futureskit.forwards import constant_maturity_grid

contracts = pd.DataFrame(
    {
        pd.Timestamp("2026-01-01"): [70.0, 71.0],
        pd.Timestamp("2026-02-01"): [71.0, 72.5],
    },
    index=pd.to_datetime(["2025-12-18", "2025-12-19"]),
)
expiries = {
    pd.Timestamp("2026-01-01"): pd.Timestamp("2025-12-19"),
    pd.Timestamp("2026-02-01"): pd.Timestamp("2026-01-20"),
}

grid = constant_maturity_grid(contracts, expiries, n_tenors=2)
print(grid.levels)     # M1/M2 prices
print(grid.changes)    # same-delivery daily changes
print(grid.contracts)  # delivery occupying each tenor
```

## Core Components

### 1. Notation Parsing

The `FuturesNotation` class handles multiple formats:

```python
from futureskit import FuturesNotation

notation = FuturesNotation()

# Regular contracts
notation.parse('BRN_2026F')    # Canonical format
notation.parse('BRN26F')       # Short year
notation.parse('BRNF26')       # Month first
notation.parse('BRN-26F')      # With separator

# Strict contract identity (does not accept vendor aliases or bare roots)
contract = notation.parse_canonical_contract('BRN_2026F')
contract.kind                  # 'contract'
notation.parse_canonical_contract('BRN')  # None
notation.parse_canonical_contract('BRN_2026A')  # None (not canonical)

# Supported unqualified references (canonical, legacy, or continuous)
notation.parse_contract_reference('BRN_2026Z')  # Canonical monthly
notation.parse_contract_reference('BRN26Z')      # Legacy monthly alias
notation.parse_contract_reference('BRNZ26')      # Month-first alias
notation.parse_contract_reference('BRN-2026Z')   # Separated full-year alias
notation.parse_contract_reference('BRN.n.1')     # Continuous reference
notation.parse_contract_reference('BRN_M01')     # Continuous M-notation
notation.parse_contract_reference('Corn_CBOT.USD_M05')  # Dotted DataDB root
notation.parse_contract_reference('ICE:BRN26Z')  # None (feed-qualified)

# Continuous contracts
notation.parse('BRN.n.1')      # Front month by open interest
notation.parse('CL.v.3')       # Third month by volume
```

### 2. Vendor RIC Formatting

Vendor symbol spelling lives in `futureskit.vendors`, one module per vendor, and
is deliberately not re-exported from the package root: the import line should
say which vendor a caller depends on.

```python
from futureskit.vendors.lseg import contract_code_from_ric, format_ric_contract

format_ric_contract("CL", "H", 2026, "NYMEX")  # "CLH26"
format_ric_contract("LCO", "V", 2026, "ICE")   # "LCOV6" - one-digit year on ICE
contract_code_from_ric("CLH26")                # "H26"
```

The contract-year width is keyed by exchange rather than global, and an
unregistered venue raises rather than defaulting. A guessed width still produces
a well-formed RIC, so the vendor reports no such instrument and the symptom
looks like a missing entitlement instead of a formatting bug.

### 3. Expiry Schedules

Curated expiries are the durable input; inference is a fallback. `merge_expiry_dates`
layers a curated map over the frame's own observations and returns a map keyed on the
frame's columns, ready to pass as `expiry_dates`:

```python
from futureskit.forwards import BEYOND_SAMPLE, infer_expiry_dates, merge_expiry_dates

# Every column, inferred from the gap between its last quote and the sample end.
inferred = infer_expiry_dates(contracts)

# Curated wins per column; uncurated columns fall back to inference.
schedule = merge_expiry_dates(contracts, curated_expiries)
grid = constant_maturity_grid(contracts, schedule, n_tenors=3)
```

**Only an observation gap before the end of the sample proves an expiry.** A column
whose last valid observation falls strictly before the last printing day stopped
trading while the board carried on, and that gap is the evidence. A column still
quoted on the last printing day was not observed to expire at all, and inference says
so with `BEYOND_SAMPLE` rather than naming the sample's end date. That matters most on
a short window — a handful of observation days across a full board, which is what a
live screen fetches — where taking the window's end for an expiry declares the whole
board expired there and rolls an uncurated front month out of M1 on the final row.

**A monthly contract cannot be live after its delivery month ends.** Some venues
keep publishing a terminal settlement for a contract that has already expired — ICE
cleared swaps do — so the series has no gap at expiry and inference on its own reads
the dead contract as alive. Where a column label is anchored on a month start — a
date-like label at midnight on the first of a month, the only label shape that names
a delivery month — the inferred expiry is capped at the last calendar day of that
month, so a September observation never selects an August delivery. The cap reads
the column label and nothing else: no expiry table, no exchange calendar, no
per-root rule. A curated expiry is never capped. Every other label is left alone,
including a *dated* one such as `2026-08-15`, which is a prompt point or an
assessment date rather than a monthly delivery.

Inference has exactly four outcomes, and they are stable to depend on:

| Column's last valid observation | Inferred expiry | Occupancy |
| --- | --- | --- |
| Before the last printing day | that observation | rolls in-sample |
| On the last printing day, delivery month still running | `BEYOND_SAMPLE` | live to the last row, never rolls |
| Running past a month-start label's month that ended first | that month's last day | rolls off at month end |
| None — never observed | `NaT` | never selected |

The capped date is a real expiry, so `roll_days` steps back from it exactly as from
any other.

`BEYOND_SAMPLE` is a plain timezone-naive `Timestamp`, so a merged schedule is a
valid `expiry_dates` argument on a windowed frame with no unwrapping. Selection under
inference then matches what curated expiries beyond the window give.

A curated key naming no column is ignored rather than widening the schedule. A
*partial* explicit `expiry_dates` map raises rather than guessing, as does one
carrying a never-observed column's `NaT`.

### 4. Vendor TradingView Notation

TradingView spells a dated contract with a full four-digit year, and qualifies a symbol
differently on a chart than in an overview path. Both spellings are public because
neither is derivable from the other. URL assembly stays with the consumer:

```python
from futureskit.vendors.tradingview import (
    tradingview_chart_symbol,
    tradingview_continuous_symbol,
    tradingview_contract_symbol,
    tradingview_overview_symbol,
)

tradingview_contract_symbol("BRN", 2026, "H")       # "BRNH2026"
tradingview_continuous_symbol("BRN", 1, "ICEEUR")   # "ICEEUR:BRN1!"
tradingview_chart_symbol("BRN", "ICEEUR")           # "ICEEUR:BRN"
tradingview_overview_symbol("BRN", "ICEEUR")        # "ICEEUR-BRN"
```

### 5. Continuous and Constant-Maturity Futures

Build continuous levels or an auditable constant-maturity grid from contract
matrices:

```python
from futureskit.forwards import (
    ExpiryOffset,
    RollSpec,
    constant_maturity_grid,
    generate_series,
)

spec = RollSpec(
    depth=2,
    month_filter=(12,),
    roll_rule=ExpiryOffset(days=1),
)
red_december = generate_series(contracts, expiries, roll_spec=spec)
grid = constant_maturity_grid(
    contracts, expiries, n_tenors=3, roll_spec=spec
)
```

``depth`` selects the Nth eligible delivery and ``month_filter`` restricts the
eligible delivery months; the grid above is therefore labelled ``M2`` through
``M4``. A column is live on its inclusive roll date. ``ExpiryOffset(days=N)``
preserves the legacy ``roll_days=N`` convention: exactly ``N`` printing days
before the anchor. Marketplace ``rollDays=N`` matches it exactly at ``N=0`` and
``N=1``; above that Marketplace subtracts calendar days and snaps forward to
the next trading day, so no exact mapping exists. Cross-product rolls can
supply an immutable expiry schedule through ``RollSpec(anchor_expiries=...)``
instead of ``expiry_dates``.

Adjustment modes are declared by ``Adjustment``. ``generate_series`` supports
backward and forward spread or ratio adjustment, plus the observation-based
linear blend named by both ``PERPETUAL`` and ``INTERPOLATED``. A missing
roll-date leg is a neutral adjustment; ratio adjustment raises when its
roll-date denominator is zero.

Rolling spreads and flies weight those continuous tenors, and a forward
projection rolls the same structure through today's curve:

```python
from futureskit.forwards import forward_rolling_structure, rolling_structure

fly = rolling_structure(contracts, {1: 1, 2: -2, 3: 1}, expiries)  # "M1-2M2+M3"
ahead = forward_rolling_structure(
    contracts.iloc[-1], expiries, {1: 1, 2: -2, 3: 1}, start=contracts.index[-1]
)
```

``weights`` maps tenor to leg weight, so each tenor appears once. The forward
requires a curated ``expiry_dates`` map, holds the curve flat and uses the
history's roll rule, counting Monday-to-Friday trading days past ``start``.
A curve entry with no expiry raises by default; ``on_missing_expiry="truncate"``
instead cuts the curve at the first such delivery and projects what precedes
it, since skipping a delivery would shift every later leg.

## Month Codes

Futures month codes follow standard conventions:
- F = January
- G = February  
- H = March
- J = April
- K = May
- M = June
- N = July
- Q = August
- U = September
- V = October
- X = November
- Z = December

## Architecture

```
futureskit/
├── notation.py      # Contract reference parsing - grammar only, no vendor spelling
├── vendors/         # How each vendor spells a contract
│   ├── lseg.py             # LSEG RIC, contract-year width keyed by exchange
│   └── tradingview.py      # TradingView, four-digit year and two qualifications
├── forwards/        # Pure contract-matrix curve construction
│   ├── _occupancy.py       # The single engine deciding which delivery occupies which tenor
│   ├── continuous.py       # Continuous series and adjustment
│   ├── constant_maturity.py# Constant-maturity tenor grid
│   ├── rollspec.py         # RollSpec, ExpiryOffset, Adjustment
│   ├── schema.py           # The input frame contract
│   ├── spreads.py, fly.py, quarterly.py, calendar.py, structure.py
│   └── util.py
└── exceptions.py    # Custom exceptions
```

## Testing

Run the complete locked test suite:

```bash
uv run --locked --no-config pytest tests/
```

Run coverage from the same environment:

```bash
uv run --locked --no-config pytest --cov=futureskit tests/
```

The `dev` group also provides Black, Flake8, and mypy for incremental cleanup.
The repository-wide legacy style and typing baselines are not currently clean,
so those tools are not CI gates for this migration.

Build the wheel and source distribution using the locked project metadata:

```bash
uv build --no-config --no-sources --wheel --sdist
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
