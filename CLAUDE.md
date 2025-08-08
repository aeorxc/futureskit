# FuturesKit Architecture Guide

This document captures key architectural decisions and implementation details for the futureskit library. This is intended for Claude AI assistants to understand the codebase structure and design principles.

## Overview

FuturesKit is a Python library for parsing and working with futures contract symbols and notation. It provides:
- Notation parsing for various futures formats
- Vendor-specific symbol conversion (TradingView, Refinitiv, Bloomberg, etc.)
- Continuous futures series modeling
- Contract chain management

## Key Architectural Decisions

### 1. Vendor Symbol Formats

The library supports converting futures symbols to various vendor-specific formats through the `SymbologyConverter` class.

**Design Pattern**: Static methods with high-level convenience wrappers
- Low-level methods: `to_tradingview_format(parsed, vendor_map)` - take ParsedSymbol
- High-level methods: `tradingview(root, vendor_map, year, month)` - build ParsedSymbol internally

**No separate formatter classes** - all formatting logic consolidated in SymbologyConverter to avoid unnecessary abstractions.

### 2. Object Relationships and Vendor Mapping

**Key Design**: Vendor mappings flow through object relationships, not stored redundantly

```python
# Object hierarchy
Future (has vendor_map)
  ├── FuturesContract (has reference to Future)
  └── ContinuousFuture (has reference to Future)
```

- `Future` stores the `vendor_map` as single source of truth
- `FuturesContract` has `future` reference, accesses vendor_map through it
- `ContinuousFuture` has `future` reference, accesses vendor_map through it

### 3. Formats Property Pattern

Both `FuturesContract` and `ContinuousFuture` expose a `formats` property that provides vendor-specific formatting:

```python
# For specific contracts
contract.formats.tradingview()  # Returns "ICEEUR:BRNH25"
contract.formats.refinitiv()    # Returns "LCOH5"

# For continuous series  
continuous.formats.tradingview()  # Returns "ICEEUR:BRN1!"
continuous.formats.refinitiv()    # Returns "LCOc1"
```

**Implementation**: Uses `functools.partial` to bind parameters:
- FuturesContract binds year/month
- ContinuousFuture binds continuous_index (depth)

**No new classes introduced** - just inline namespace objects and partial functions.

### 4. Vendor Map Structure

Vendor maps contain platform-specific symbol mappings:

```python
vendor_map = {
    'tradingview_symbol': 'BRN',      # TradingView root symbol
    'tradingview_feed': 'ICEEUR',     # TradingView exchange feed
    'refinitiv_symbol': 'LCO',        # Refinitiv RIC root
    'marketplace_symbol': 'BRN',       # Marketplace root
    'marketplace_feed': 'ICE_EuroFutures',  # Marketplace feed
    # ... other vendor mappings
}
```


## Important Implementation Notes

### ParsedSymbol
- Core data structure for parsed futures notation
- Contains: root, year, month, is_continuous, contract_index, roll_rule
- Used internally by SymbologyConverter methods

### FuturesNotation
- Main parser for various futures formats (underscore, ICE, CME, etc.)
- Extended to handle internal marked symbols like `OIL_BRENT_DATED_2025H`
- Uses regex patterns for flexible parsing

### No VendorFormatter Class
- Initially considered but removed to avoid unnecessary abstraction
- All vendor formatting consolidated in SymbologyConverter
- Simpler architecture with single responsibility

## Common Patterns to Follow

1. **Avoid creating new classes** unless absolutely necessary
2. **Use partial functions** for binding parameters to methods
3. **Store data in one place** - avoid redundancy (vendor_map only in Future)
4. **Use property decorators** for computed/formatted values
5. **Import inside methods** when needed to avoid circular imports

## Testing Approach

- Mock datasources for unit tests
- Use real Future/Contract objects in integration tests
- Test vendor format outputs against known examples
- Verify object relationships and data flow

## Future Enhancements Under Consideration

1. URL generation methods for vendor platforms
2. More vendor format support (ICE Direct, CME Globex, etc.)
3. Automatic vendor_map building from exchange metadata
4. Contract specification enrichment from exchange data