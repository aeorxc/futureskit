# futureskit

A Python library for parsing and working with futures contract symbols and notation.

## Overview

futureskit provides a comprehensive toolkit for working with futures contracts, including:

- **Futures notation parsing** - Parse various futures formats (`BRN_2025F`, `BRN25F`, `BRN.n.1`)
- **Symbol conversion** - Convert between different vendor conventions (CME, ICE, Bloomberg)
- **Contract representations** - First-class objects for futures contracts and chains
- **Dynamic field support** - Access any fields your data provider supplies
- **Continuous futures** - Build continuous series with configurable roll rules

## Installation

```bash
pip install futureskit
```

## Quick Start

```python
from futureskit import Future, FuturesNotation, SymbologyConverter

# Parse futures notation
notation = FuturesNotation()
parsed = notation.parse('BRN_2026F')
print(f"Root: {parsed.root}, Year: {parsed.year}, Month: {parsed.month}")

# Convert between vendor formats
converter = SymbologyConverter()
print(converter.to_cme_format(parsed))       # @BRN26F
print(converter.to_bloomberg_format(parsed))  # COF6 Comdty

# Work with futures objects (requires data source)
wti = Future('CL', datasource=my_datasource)
mar_contract = wti.contract(2026, 'H')
print(mar_contract.close)  # Access price data
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

# Continuous contracts
notation.parse('BRN.n.1')      # Front month by open interest
notation.parse('CL.v.3')       # Third month by volume
```

### 2. Symbol Conversion

Convert between different vendor conventions:

```python
from futureskit import SymbologyConverter

converter = SymbologyConverter()
parsed = notation.parse('BRN_2026F')

# Different vendor formats
converter.to_cme_format(parsed)         # @BRN26F
converter.to_ice_format(parsed)         # BRN26F
converter.to_bloomberg_format(parsed)   # COF6 Comdty
converter.to_short_year_format(parsed)  # BRN26F
```

### 3. Futures Objects

The `Future` class provides a high-level interface:

```python
from futureskit import Future

# Create a Future object with your data source
wti = Future('CL', datasource=my_datasource)

# Access specific contracts
mar_26 = wti.contract(2026, 'H')
mar_26_alt = wti['H26']  # Shorthand access

# Dynamic field access (depends on data source)
print(mar_26.close)           # Price data
print(mar_26.volume)          # Volume data
print(mar_26.tick_size)       # Contract specs
print(mar_26['custom_field']) # Dictionary-style access
```

### 4. Contract Chains

Work with collections of contracts:

```python
# The Future object maintains a chain of contracts
print(f"Available contracts: {len(wti.chain)}")

# Get front month contract
front = wti.chain.get_front_month()

# Get nth contract
third_month = wti.chain.get_nth_contract(3)
```

### 5. Continuous Futures

Create continuous series (currently with placeholder implementation):

```python
continuous = wti.continuous(
    roll='calendar',  # Roll rule
    offset=-5,        # Days before expiry
    adjust='back'     # Adjustment method
)
```

## Data Source Integration

To use futureskit with your data, implement a data source:

```python
class MyDataSource:
    def get_contract_chain(self, root: str):
        """Return list of available contracts"""
        return [
            {'year': 2026, 'month_code': 'H'},
            {'year': 2026, 'month_code': 'M'},
            # ...
        ]
    
    def get_futures_contract(self, root: str, year: int, month: str) -> pd.DataFrame:
        """Return time series data"""
        return pd.DataFrame({
            'close': [...],
            'volume': [...],
            # Any fields you have
        })
    
    def get_contract_specs(self, root: str, exchange: str = None) -> dict:
        """Return contract metadata"""
        return {
            'tick_size': 0.01,
            'contract_size': 1000,
            # Any metadata
        }
```

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
├── notation.py      # Symbol parsing logic
├── contracts.py     # Contract and chain representations
├── futures.py       # High-level Future and ContinuousFuture classes
├── symbology.py     # Symbol format conversion
└── exceptions.py    # Custom exceptions
```

## Examples

See the `examples/` directory for:

- `basic_usage.py` - Getting started examples
- `flexible_futures_demo.py` - Dynamic field capabilities with different providers

## Testing

Run tests with pytest:

```bash
pytest tests/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.