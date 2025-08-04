# FuturesKit Design Document

## Overview

FuturesKit is a Python library for parsing and working with futures contract symbols and notation. It provides first-class objects for futures contracts, continuous series, and forward curves.

## Current Implementation

### Core Object Model

The library implements a flexible, data-provider-agnostic model for futures:

#### 1. FuturesContract
- Represents a specific futures contract (e.g., BRN March 2026)
- Dynamic attribute access for price series and metadata
- Supports any fields provided by data sources
- Methods: `to_canonical()`, `to_short_year()`, comparison operators

#### 2. ContractChain
- Collection of futures contracts for a single commodity
- Automatically sorted by delivery date
- Methods to get front month, nth contract, specific contract

#### 3. Future
- Main factory class representing a futures product line (e.g., 'CL' for WTI)
- Creates FuturesContract objects with data from providers
- Provides shorthand access: `wti['H26']` returns March 2026 contract
- Can create ContinuousFuture objects

#### 4. ContinuousFuture
- Represents a continuous futures series
- Configurable roll rules and adjustments
- Currently has placeholder implementation for evaluation

### Notation Parsing

The `FuturesNotation` class handles multiple formats:
- Canonical: `BRN_2026F`
- Short year: `BRN26F` or `BRNF26`
- With separators: `BRN-26F`, `BRN 26F`
- Continuous: `BRN.n.1` (front month by open interest)

Supported roll rules for continuous contracts:
- `n`: Open interest
- `v`: Volume
- `c`: Calendar
- `fn`: First notice
- `lt`: Last trade

### Symbology Conversion

The `SymbologyConverter` class converts between vendor formats:
- CME: `@BRN26F`
- ICE: `BRN26F`
- Bloomberg: `COF6 Comdty`
- Marketplace continuous: `BRN_001_MONTH`

## Key Design Features

### 1. Dynamic Field Access
Contracts can access any field provided by the data source:
```python
contract.close  # Standard field
contract.marker_settle  # ICE-specific field
contract.implied_volatility  # Provider analytics
contract['custom_field']  # Dictionary-style access
```

### 2. Provider Agnostic
The same contract object works with different data providers:
- ICE: Provides marker_settle, block_volume, efs_volume
- CME: Provides vwap, globex_volume, pit_volume
- Bloomberg: Provides px_last, px_bid, rsi_14d

### 3. Lazy Loading
Data is only loaded when a datasource is provided, keeping objects lightweight.

## Architecture Decisions

### 1. Separation of Concerns
- **Notation**: Parsing and symbol manipulation
- **Contracts**: Data representation and access
- **Symbology**: Format conversion between vendors
- **Futures**: High-level factory and operations

### 2. No Inheritance for Instruments
Unlike the proposed design, the current implementation doesn't use an abstract base class for instruments. This keeps the design simpler while maintaining flexibility.

### 3. Month Code Consolidation
`MONTH_CODES` and `MONTH_TO_CODE` are defined in `notation.py` and imported where needed, avoiding duplication.

## Dependencies

- `pandas`: For time series data handling
- `python-dateutil`: For date parsing and manipulation

## Future Enhancements

### 1. Complete ContinuousFuture Implementation
- Implement roll schedule generation
- Build proper series stitching
- Add adjustment methods (back-adjust, forward-adjust)

### 2. Forward Curve Support
- Add FuturesCurve class for term structure
- Implement interpolation methods
- Support curve analytics

### 3. Data Source Integration
- Standardize data source interface
- Add contract discovery methods
- Implement caching layer

### 4. Advanced Features
- Roll calendar management
- Spread contracts
- Options on futures support
- Seasonal patterns analysis

## Migration from String-Based Systems

FuturesKit is designed to integrate with existing string-based systems:
1. Parse existing notation into objects
2. Use objects internally for rich functionality
3. Convert back to strings for legacy systems
4. Gradual migration path

## Testing Strategy

The library includes comprehensive tests for:
- Notation parsing (all formats and edge cases)
- Symbology conversion
- Dynamic field access
- Contract comparisons and sorting

## Performance Considerations

- Lightweight objects until data is needed
- Efficient parsing with compiled regex patterns
- Minimal dependencies
- Cache-friendly design for repeated operations