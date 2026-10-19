# Changelog

## 1.2.0 - 2026-10-08

### Added
- `forwards.forward_rolling_structure(..., on_missing_expiry="raise" | "truncate")`. The
  default `"raise"` keeps current behaviour. `"truncate"` cuts the curve and its expiries at
  the first delivery, in curve order, whose expiry is absent or null and projects the rest; a
  curve with no usable front delivery returns an empty, correctly named float series. Lifted
  from oil-pricing-dashboard's `_structure_forward`, which truncated the curve by hand.

### Deprecated
- `generate_structure_series(mx_df=..., my_df=...)` emits a `DeprecationWarning` and will be
  removed in 2.0. It still subtracts the prebuilt series as before. `recent_structure`, its
  only internal caller, now builds each spread through `rolling_structure`; values, labels and
  index are unchanged, pinned by a regression test against the 1.1.0 implementation.

### Fixed
- The occupant engine no longer builds a unit-less `np.datetime64("NaT")`, which raised NumPy's
  "generic unit for NumPy timedelta is deprecated" warning whenever a schedule carried a `NaT`
  expiry. The suite now passes under `-W error::DeprecationWarning`.

## 1.1.0 - 2026-10-07

### Added
- **`forwards.rolling_structure(contracts, weights, expiry_dates, roll_days, *, trim=None)`**
  stitches any weighted tenor structure (`{1: 1, 6: -1}` for M1-M6, `{1: 1, 2: -2, 3: 1}` for
  a fly) along the canonical occupant engine. Its `trim` hook receives every fixed instance the
  roll visits as one full-history column (a `MultiIndex` of leg deliveries) and may blank noisy
  cells — e.g. `commodutil.stats.trim_expiry_noise` — before stitching, so expiry noise is cut
  per contract rather than from the stitched series. Untrimmed, it equals the weighted sum of
  `generate_series` tenors. Lifted from oil-pricing-dashboard's screener, whose private
  `_trimmed_rolling_reference` it reproduces exactly.
- **`forwards.forward_rolling_structure(curve, expiry_dates, weights, roll_days=0, *, start,
  horizon_months=24)`** projects a `rolling_structure` forward from one curve: it runs
  `rolling_structure` over the curve held flat on `start` and every business day after it, so
  the forward rolls by the history's rule, counting Monday-to-Friday trading days past the
  sample. A weekend expiry therefore counts back from the Friday, one day earlier than a
  business-day offset from the raw date. A curated `expiry_dates` map covering every curve
  entry is required; `None` raises rather than inferring expiries from the flat quotes.

### Changed
- `generate_structure_series` is now a wrapper over `rolling_structure` with weights
  `{mx: 1, my: -1}`. Values, the `M{mx}-M{my}` label, dtype and index are unchanged, pinned
  by a regression test against the 1.0.5 implementation. One observable difference: the
  result no longer carries the continuous series' `attrs["mask_switch"]`, which 1.0.5 leaked
  onto the spread. The prebuilt `mx_df`/`my_df` path keeps its direct subtraction, so unsigned
  dtypes, the column-axis name and `attrs` are unchanged there.

## 1.0.5 - 2026-10-06

### Fixed
- **`roll_days` is honoured when the expiry lies beyond the sample.** `determine_roll_date`
  returned the expiry unadjusted when it fell after the last observation, so a live front
  contract ignored `roll_days` until its expiry entered the sample and those days were then
  restated. A continuous or structure series now rolls on the same date whether or not the
  expiry is inside the sample.

### Removed
- Removed the dead `forwards.util.futures_month_conv` and `forwards.util.futures_month_conv_inv`
  aliases.

## 1.0.4 - 2026-09-09
### Fixed
- **`exclude_price_month` no longer truncates live structures.** The final
  calendar month is now removed only from contract columns that stopped
  printing before the frame's latest print, and monthly flies no longer apply
  the exclusion twice.

## 1.0.3 - 2026-09-04
### Fixed
- **Strips no longer fail on a never-observed leg.** `strip_mean` built its listing and
  expiry bounds with `np.array([...], dtype="datetime64[ns]")`, which on current numpy and
  pandas rejects the float form of `NaT`, so any strip touching an all-empty delivery column
  raised `TypeError: 'float' object cannot be interpreted as an integer` (CME NymexFutures
  `ARY` carries seven empty 2022 columns; every quarterly panel over them went blank). The
  bounds are now built through `pd.to_datetime`, so `NaT` survives and the liveness rule
  that always governed applies: a never-observed leg is never live and never required, and
  a strip with no live leg is `NaN`. No strip that previously succeeded changes.

## 1.0.2 - 2026-09-03
### Fixed
- **An inferred expiry is now capped at the end of its delivery month.** Some venues keep
  publishing a terminal settlement for a contract that has already expired — ICE cleared swaps do
  — so the series carries no observation gap at expiry and last-observation inference read the dead
  contract as alive to the end of the sample. Over an early-September window the expired August
  swap was still quoted on every row, inferred `BEYOND_SAMPLE`, and occupied M1: a September
  observation selected an August delivery, and every tenor behind it shifted by one.

  Owner ruling (2026-09-03): a monthly contract cannot be live after its delivery month ends. For
  an **uncurated** column whose label is anchored on a month start — a date-like label at midnight
  on the first of a month — the inferred expiry is now `min(current inference, last calendar day
  of that month)`. The August column above expires 2026-08-31 and never occupies a September row.

  This is grammar, not a calendar: the cap reads the column label and nothing else, so futureskit
  still holds no expiry table, no holiday calendar and no per-root rule. Column labels remain opaque
  to the schema, which neither requires nor interprets a delivery month; a month start is simply the
  only label shape that names one. Every other label is left uncapped, including a *dated* label
  such as `2026-08-15`, which is a prompt point or an assessment date rather than a monthly delivery.
  Curated expiries are never capped — curated wins, inside or past the delivery month. A delivery
  whose month has not ended by the last printing day still infers `BEYOND_SAMPLE` and stays live,
  and a never-observed column still infers `NaT`. The capped date is a real expiry, so `roll_days`
  steps back from it exactly as from any other expiry; where the month end is not a printing day the
  roll anchors on the last printing day on or before it, as it does for any expiry.

### Changed
- **Inference now has four outcomes rather than three.** The fourth is the delivery month's last
  day, described under Fixed above. Consumers pinning to the outcome set should read the table
  below; nothing that was a date, `BEYOND_SAMPLE` or `NaT` changes meaning.

- **`forwards.util.extract_expiry_dates_from_contracts` now delegates to `infer_expiry_dates`.** The
  deprecated function carried its own inference — a bare last-observation read with no gap guard
  and no delivery-month cap — and its result validates as a complete expiry map, so passing it back
  into a continuous-series call reproduced in full the bugs the canonical engine fixes. There is
  now exactly one inference rule in the package. Two visible consequences, both of them why it was
  deprecated: it no longer deduplicates shared expiry dates, so a ladder built on it keeps the
  far-tenor tail it used to lose, and a column quoted through the sample now yields `BEYOND_SAMPLE`
  rather than the sample's end date. It still emits its `DeprecationWarning`.

## 1.0.1 - 2026-09-02
### Fixed
- **Expiry inference no longer reads the end of the sample as an expiry.**
  `infer_expiry_dates` took each column's last valid observation as its expiry,
  so on a windowed frame — a short observation range across a full board, which
  is what a live desk screen fetches — every contract still quoted on the final
  row was declared to expire on that row. Measured on a real eight-day window
  over Brent Dated: 139 deliveries, curated expiries reaching only to Dec-2028,
  and all 106 uncurated deliveries from Jan-2029 to Oct-2037 handed the window's
  last row as their expiry.

  Only an observation gap proves an expiry. A column whose last valid
  observation falls strictly before the last printing day stopped trading while
  the board carried on, and it keeps its inferred expiry. Trailing rows on which
  no column printed do not end the sample.

  The visible symptom was a front contract with no curated expiry being rolled
  out of M1 on the final row of a short window, with `roll_days` stepping back
  from a date that was never an expiry. Selection over a window now matches what
  curated expiries beyond that window produce.

### Added

- **`forwards.BEYOND_SAMPLE`** — the expiry of a contract observed to be alive
  at the end of the sample. A column still quoted on the last printing day now
  infers this constant instead of the sample's end date. It is a plain
  timezone-naive `Timestamp` (`2200-01-01`), so it validates, sorts and compares
  as any expiry does, and every engine already treats an expiry beyond the last
  observation as never rolling in-sample. Nothing in the schema or occupancy
  layer needs to special-case it.

  It is deliberately **not** `NaT`. `NaT` continues to mean "never observed,
  therefore never live", unchanged and still load-bearing; one token cannot mean
  both "never selected" and "always selected". The inference outcomes are
  distinct and each is stable to depend on:

  | Column's last valid observation | Inferred expiry | Occupancy |
  | --- | --- | --- |
  | Before the last printing day | that observation | rolls in-sample |
  | On the last printing day, delivery month still running | `BEYOND_SAMPLE` | live to the last row |
  | Running past a month-start label's month that ended first | that month's last day | rolls off at month end |
  | None — never observed | `NaT` | never selected |

  `pd.Timestamp.max` was considered and rejected: it overflows on the first
  offset a consumer adds to it.

### Changed

- **`merge_expiry_dates` output is now re-usable on a windowed frame.** Because
  an uncurated but live column takes `BEYOND_SAMPLE` rather than `NaT`, the
  merged schedule passes `validate_expiry_dates` and can go straight back in as
  an `expiry_dates` argument, which is what the README documents. A schedule
  containing a never-observed column's `NaT` is still rejected as incomplete,
  unchanged: a curated map with a hole in it is a mistake worth raising on.

- **A strip read over a short window is the strip again.** `strip_mean` derives
  leg liveness from the same inference, so on a window where every leg was still
  quoted at the end each leg used to read as expired and calendars, quarters and
  seasons went `NaN`. Legs quoted through the sample end are live and required.
  No change to `strip_mean` itself was needed; it inherits the corrected
  inference.

- **A strip no longer requires a leg that has not listed yet.** Liveness was
  bounded at one end only: a leg counted as live wherever it was unexpired and
  had data somewhere in the frame, so a delivery whose first quote came later
  read as "live but unquoted" beforehand and blanked the strip. The deliveries
  of a far year list one by one, so every calendar lost its birth — the stretch
  from the year's first quote until the last of its twelve months started
  printing. Brent CAL 2026 lost 2023-05-30 to 2023-12-28; across the desk's
  charts that was 2,554 blanked cells in `oilpricingcharts` and 2,131 in
  `debbiestrats`.

  A leg is now live between its first valid observation and its expiry, which
  is what "every leg live at that date" always meant: listed **and** unexpired.
  A listed, unexpired leg with no quote still withholds the strip, which is the
  case the rule exists for. A never-observed leg is never live, unchanged.
  Values on rows a strip already produced do not move: on the CL fixture the
  Summer 2022 half-year gains 757 leading observations and every one of its
  1,019 existing rows is identical.

  Tenor selection is deliberately not changed to match. A strip is a number
  that must be right or absent, but a tenor is an identity: M2 is the second
  delivery whether or not it has started trading, and excluding an unlisted
  delivery would promote M3 into M2 and shift the whole ladder. An unlisted
  tenor already prices `NaN`, which is the right answer, and its slot is
  waiting when the contract lists.

## 1.0.0 - 2026-09-02

### Breaking

- Removed the deprecated object model: `Future`, `FuturesContract`,
  `ContractChain`, `FuturesDataSource`, and `TradingViewDataSource`.
- **Removed the `futureskit.datasources` subpackage entirely**, including
  `LsegDataSource` and the retired-brand `RefinitivDataSource` alias. Its data
  methods were never implemented and raised `NotImplementedError`; what did
  work was URL generation, which is the consumer's job and is the same line
  `TradingViewDataSource`'s replacement draws. No repository imported it. A
  Refinitiv or LSEG integration targets the frame contract in
  `forwards/schema.py`, not a datasource class, and vendor symbol spelling now
  lives in `futureskit.vendors`. futureskit fetches nothing at all.
- The removed classes never emitted `DeprecationWarning` at runtime. This
  breaking removal must therefore be called out prominently in the 1.0.0
  release notes.
- Removed `forwards.util.extract_expiry_date`. It fabricated an expiry for any
  unmapped contract by adding `MonthEnd(1)`, so a missing or mismatched expiry
  map produced a plausible roll date instead of an error. It had no callers in
  this package, and the downstream guards written against that fallback can go.
- **A strip now requires every leg still live on the observation date.**
  `cal_contracts` averaged with a plain `.mean(axis=1)`, so a row on which a
  still-trading month had no print silently published the average of the months
  that did, under the CAL's name. Quarters and half-years withheld the strip
  instead. The three now share one rule: a delivery that has already expired is
  not missing data and is neither required nor averaged in, so a part-expired
  calendar prints the balance of its year; a delivery that is still live but
  unquoted withholds the value.

  Only the second case changes behaviour. CAL 2020 on 2020-01-02 still prints
  59.174, the eleven-month balance with January expired. What used to be a
  quiet partial average, and is now `NaN`, is the row where a live month has no
  quote.

  Liveness is read from the data, never from a calendar: a leg is expired at a
  date when its last valid observation falls strictly before it, the same
  inference `infer_expiry_dates` applies. The new keyword-only `expiry_dates`
  on `cal_contracts`, `quarterly_contracts`, `calculate_quarter`,
  `half_year_contracts`, `all_spread_combinations` and `spread_combination`
  supplies a curated map instead, mirroring the continuous-series entry points.
  A delivery never observed is never live and never required.

  The keyword-only `min_legs` on the same functions lowers the bar explicitly:
  it is the number of live legs that must carry a quote, so `min_legs=1`
  averages whatever is live and quoted.
- **Vendor symbol spelling moved to `futureskit.vendors` and is no longer
  re-exported from the package root or from `futureskit.notation`.** The new
  import paths are `futureskit.vendors.lseg` for `format_ric_contract`,
  `contract_code_from_ric`, `ric_year_digits`, `CME_GROUP_EXCHANGES` and
  `ONE_DIGIT_YEAR_EXCHANGES`, and `futureskit.vendors.tradingview` for
  `tradingview_chart_symbol`, `tradingview_overview_symbol`,
  `tradingview_contract_symbol` and `tradingview_continuous_symbol`. Names,
  signatures and outputs are unchanged; only the import path moves, and 1.0.0
  is the moment to make it honest rather than leaving an alias to unpick later.
  Each module is named for its vendor rather than for the notation it uses: a
  RIC is LSEG's symbology, not a vendor in its own right.
- **The strip and spread builders return an empty frame instead of `None` or
  raising.** `cal_contracts` returned an empty frame, `cal_spreads`,
  `quarterly_contracts` and `fly_quarterly` returned `None` implicitly,
  `half_year_contracts` raised from `pd.concat([])`, and `all_quarterly_flys`
  concatenated a list that could contain `None`. All of them now return a
  DataFrame with no columns carrying the input's index, so a caller can index
  the result without first testing it for `None`.

### Added

- `forwards.infer_expiry_dates(contracts)` is now public: one expiry per frame
  column, taken from that column's last valid observation, with `NaT` for a
  column that was never observed. It does not deduplicate, so shared expiry
  dates no longer cost a ladder its far-tenor tail.
- `forwards.merge_expiry_dates(contracts, curated)` layers a curated expiry map
  over that inference. Curated wins per column, uncurated columns fall back to
  inference, and the result is keyed on the frame's columns so it feeds
  `expiry_dates` directly. An uncurated, never-observed column surfaces as
  `NaT` rather than vanishing from the schedule and shifting later deliveries
  into earlier tenors.
- `ParsedSymbol.delivery_month` (and the equivalent `to_date()`) returns the
  first of the delivery month for a dated contract, and `None` for quarters,
  calendars, continuous series, and permissive parses that never asserted
  contract identity. A dated contract carrying a non-futures month code raises
  `InvalidMonthCodeError` rather than returning `None`.
- TradingView vendor symbol notation: `tradingview_contract_symbol`,
  `tradingview_continuous_symbol`, `tradingview_chart_symbol` and
  `tradingview_overview_symbol`, exported from the package root beside the
  RIC builders. TradingView spells a dated contract with a full four-digit
  year (`BRNH2026`) — a third contract-year width beside CME Group's two
  digits and ICE's one — and qualifies a symbol as `FEED:SYMBOL` on a chart
  but `FEED-SYMBOL` in an overview path. Both qualification spellings are
  public as `tradingview_chart_symbol` and `tradingview_overview_symbol`: a
  consumer assembling either URL family needs the one matching its surface,
  and neither is derivable from the other, since an unqualified code carries
  no separator at all. URL assembly itself stays with the consumer.

### Changed

- Promoted the DataFrame-based forwards surface to top-level `futureskit`
  exports, including roll specifications, continuous-series generation, and
  schema validation, and made the `futureskit.forwards` facade explicit.
- Added the `py.typed` marker so type checkers recognize futureskit as a typed
  package.
- `forwards.generate_structure_series` now accepts `expiry_dates` and passes it
  through to the continuous series it is built from. It previously always
  inferred, so a caller holding curated expiries could not use this function at
  all and had to restitch M1-M2 itself. The default `None` preserves the
  existing inferred behaviour exactly.
- The strip builders no longer read the wall clock. `cal_contracts`,
  `all_spread_combinations` and `spread_combination` take a keyword-only
  `as_of` deciding which year gets the incomplete-year carve-out, and
  `recent_spreads` takes one naming the date its relevance window is centred
  on. Both default to today, so existing calls are unchanged, but a caller
  supplying `as_of` gets a result that depends on its arguments alone rather
  than on the day the code runs. Same frame, same `as_of`, same frame out.
- `notation.py` holds contract grammar only. The test this package sorts by is
  whether a thing would be identically true at any firm with any data vendor.
  Contract grammar passes it; a RIC's contract-year width and TradingView's
  four-digit year do not, even though both are pure functions with no I/O. They
  now live in `futureskit.vendors`, one module per vendor, and the dependency
  runs one way: vendor modules read the grammar, and `notation.py` imports
  nothing from `vendors`, which a test pins.
- Quarterly and half-year strips keep every observation row. They withheld an
  incomplete row by dropping it from the leg frame before averaging, so a date
  on which no strip was complete disappeared from the result's index entirely.
  Such a row is now present and `NaN`, which is the same distinction the
  package already draws for a tenor that is never live.

### Deprecated

- `forwards.util.extract_expiry_dates_from_contracts` now emits a
  `DeprecationWarning`. Use `forwards.infer_expiry_dates`. (It deduplicated
  shared expiry dates and therefore dropped contracts; as of the entry under
  Changed above it delegates and no longer does.)

### Fixed

- **Documentation: the Marketplace roll equivalence was wrong.** Every mention
  of `roll_days=N` claimed it matched Marketplace `adjust_contract(rollDays=N+1)`,
  including the 0.7.0 release notes below. Two independent live checks against
  BRN and CL over 2015-2026, covering 281 rolls, disproved it. Marketplace
  `rollDays=N` matches `roll_days=N` exactly at `N=0` and `N=1`, bit-identical
  on every overlapping day for M1, M2 and M3, with the same inclusive-roll-date
  semantics: on the roll date both sides still hold the outgoing contract.
  Above that Marketplace subtracts *calendar* days and snaps forward to the next
  trading day, so its expiry-to-roll distance varies between one and four
  trading days at `rollDays=5` and saturates over long weekends, where
  `rollDays` 2, 3 and 5 all landed on CL 2021-01-20. futureskit's offset is
  always exactly N printing days, with no exceptions among rolls that fall
  inside the sample, so no exact mapping exists above 1. No behaviour changed;
  the claim was false when it was written. Corrected in
  `forwards/schema.py`, `generate_series`, `ExpiryOffset`, the README and
  `AGENTS.md`. The 0.7.0 entry below is left as the record of what was claimed
  at the time.

- **Back-adjustment now follows the selected tenor's own roll path.**
  `generate_series` derived every adjustment from the front-month occupancy
  path, so `front_month=2` with `back_adjust=True` (and `RollSpec` depth
  greater than one with `Adjustment.BACKWARD_SPREAD`) applied the M1 roll gap
  to a deeper tenor. On a non-parallel curve that made the series worse than
  the raw one: with an M1/M2 gap of 10 and an M2/M3 gap of 3, the adjusted M2
  carried a -6 step at the roll where the raw M2 carried +4. Each requested
  tenor is now adjusted along its own path, and roll dates are read from the
  occupancy the engine actually produced rather than recomputed from the
  outgoing delivery's expiry. `front_month=1` results are unchanged.
- **`generate_series` results survive `pd.concat` again.** pandas compares
  `attrs` with `==` in `__finalize__`, so the numpy occupancy matrix in
  `attrs["mask_switch"]` made concatenating two results raise `ValueError: The
  truth value of an array with more than one element is ambiguous`.
  `attrs["mask_switch"]` now holds the same occupancy as a nested list of
  column positions, which `pd.DataFrame(...)` accepts exactly as before.

### Removed

- `generate_series` no longer publishes `attrs["mask_adjust"]`. It was an
  undocumented diagnostic with no consumer, it is per-tenor rather than
  per-result now that each tenor is adjusted on its own path, and as a
  DataFrame it had the same `pd.concat` problem as the occupancy matrix.
- The defensive `attrs = {}` scrubs in `generate_multiple_continuous_series`,
  `quarterly_contracts`, `cal_contracts` and `spread_combination_quarter` are
  gone with the cause. Those in the strip builders also mutated the caller's
  input frame.

## 0.7.0 - 2026-08-21

### Breaking

- **Incomplete explicit expiry maps now raise ``ValueError``.** ``expiry_dates``
  and ``RollSpec.anchor_expiries`` must cover every forwards-frame column
  exactly. In 0.4.x, a missing delivery silently fell back to that delivery's
  month end, which could conceal a partial or mismatched expiry schedule.

### Changed

- `LsegDataSource` is now a standalone URL-generation class rather than a
  subclass of the deprecated object-oriented datasource interface. Its public
  methods and return values are unchanged.
- The forwards frame contract now accepts arbitrary unique column identities
  in caller-defined curve order. Continuous-series APIs preserve those labels
  and match explicit expiry maps against them exactly; columns no longer need
  to be sorted delivery-month timestamps.
- Continuous-series entry points now prefer a frozen, hashable ``RollSpec``
  describing eligible delivery months, contract depth, an ``ExpiryOffset``
  rule, adjustment convention, interpolation window, and optional
  cross-product anchor expiries. Legacy ``roll_days=N`` remains supported with
  its existing inclusive-roll-date meaning (Marketplace ``rollDays=N+1``).
- ``generate_series`` now exposes the adjustment axis through ``Adjustment``
  and implements ``FORWARD_SPREAD``, ``BACKWARD_RATIO``, ``FORWARD_RATIO``,
  ``PERPETUAL``, and ``INTERPOLATED`` along the actual occupied contract path,
  alongside the existing ``NONE`` and ``BACKWARD_SPREAD`` modes. Perpetual and
  interpolated are the same observation-based linear blend, normalized over
  the available window. Missing roll-date legs produce neutral axis
  adjustments; ratio modes reject either non-positive roll-date leg with a
  dated error, and new adjustments reject depth greater than one until
  front-roll transition dates are supported.

### Fixed

- **`generate_series` edge-case results have changed.** Continuous tenors now
  use the same canonical occupant engine as `constant_maturity_grid`. This fixes
  missing-delivery-month intervals that previously removed observations,
  preserves all-NaN delivery columns instead of shifting later contracts into
  earlier tenors, and applies `roll_days` to weekend, holiday, and other
  non-quoted expiries by anchoring on the last trading observation on or before
  expiry. Existing consumers can therefore see different values for these
  previously incorrect edge cases.
