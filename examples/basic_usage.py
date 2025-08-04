"""
Basic usage examples for futureskit

This demonstrates the new object model for working with futures.
"""

import pandas as pd
import numpy as np
from datetime import date
from futureskit import (
    Future, ContinuousFuture, 
    FuturesNotation, SymbologyConverter,
    FuturesContract, ContractChain
)


# Example data source for demonstration
class DemoDataSource:
    """Simple data source for examples"""

    def get_contract_chain(self, root: str):
        """Return a list of dicts representing available contracts."""
        # In a real scenario, this would fetch all available contracts.
        # Here, we generate a few for the next year.
        today = date.today()
        return [
            {'year': today.year, 'month_code': 'H'},
            {'year': today.year, 'month_code': 'M'},
            {'year': today.year, 'month_code': 'U'},
            {'year': today.year, 'month_code': 'Z'},
            {'year': today.year + 1, 'month_code': 'H'},
        ]

    def get_futures_contract(self, root: str, year: int, month: str) -> pd.DataFrame:
        """Generate some demo price data"""
        dates = pd.date_range(end=date.today(), periods=30, freq='B')
        np.random.seed(hash((root, year, month)) % (2**32 - 1))
        returns = np.random.randn(len(dates)) * 0.01
        close = 100 * np.exp(np.cumsum(returns))
        
        return pd.DataFrame({
            'open': close * (1 + np.random.randn(len(dates)) * 0.001),
            'high': close * (1 + abs(np.random.randn(len(dates)) * 0.002)),
            'low': close * (1 - abs(np.random.randn(len(dates)) * 0.002)),
            'close': close,
            'volume': np.random.randint(1000, 10000, len(dates)),
            'open_interest': np.random.randint(50000, 100000, len(dates)),
        }, index=dates)
    
    def get_contract_specs(self, root: str, exchange: str = None) -> dict:
        """Return contract specifications"""
        return {
            'CL': {'tick_size': 0.01, 'contract_size': 1000, 'currency': 'USD', 'exchange': 'NYMEX'},
            'BRN': {'tick_size': 0.01, 'contract_size': 1000, 'currency': 'USD', 'exchange': 'ICE'},
        }.get(root, {})


def example_1_basic_future_usage():
    """Example 1: Creating and using a Future and FuturesContract"""
    print("=== Example 1: Basic Future Usage ===\n")
    
    ds = DemoDataSource()
    
    # 1. Create a Future object for the commodity
    wti = Future('CL', datasource=ds)
    print(f"Loaded {wti.root_symbol} with {len(wti.chain)} contracts.")

    # 2. Access a specific, data-rich contract
    today = date.today()
    mar_contract = wti.contract(today.year, 'H')
    
    if mar_contract:
        # 3. Access price data from the contract
        print(f"Contract: {mar_contract.to_canonical()}")
        print(f"Latest close: ${mar_contract.close.iloc[-1]:.2f}")
        print(f"Average volume: {mar_contract.volume.mean():,.0f}")
        
        # 4. Access contract specs (metadata)
        print(f"\nTick size: ${mar_contract.tick_size}")
        print(f"Contract size: {mar_contract.contract_size} barrels")


def example_2_notation_and_symbology():
    """Example 2: Parsing notations and converting symbology"""
    print("\n\n=== Example 2: Notation and Symbology ===\n")
    
    notation = FuturesNotation()
    converter = SymbologyConverter()
    
    # Parse a canonical symbol
    parsed = notation.parse('CL_2025H')
    
    print(f"Original: CL_2025H")
    print(f"CME format: {converter.to_cme_format(parsed)}")
    print(f"Bloomberg format: {converter.to_bloomberg_format(parsed)}")

    # Use shorthand notation to get a contract from a Future object
    ds = DemoDataSource()
    wti = Future('CL', datasource=ds)
    mar_25_contract = wti['H25'] # Assuming H25 is in the generated chain
    if mar_25_contract:
        print(f"\nFetched via shorthand 'H25': {mar_25_contract}")


def example_3_continuous_future():
    """Example 3: Creating and evaluating a continuous future"""
    print("\n\n=== Example 3: Continuous Futures ===\n")
    
    ds = DemoDataSource()
    wti = Future('CL', datasource=ds)
    
    # 1. Create a continuous future definition from the main Future object
    front_month = wti.continuous(roll='calendar', adjust='back', depth=0)
    print(f"Continuous series definition: {front_month}")

    # 2. Evaluate it to get the data (Note: uses placeholder logic for now)
    continuous_data = front_month.evaluate()
    
    if not continuous_data.empty:
        print(f"Latest close from continuous series: ${continuous_data.close.iloc[-1]:.2f}")


def example_4_dynamic_fields():
    """Example 4: Working with provider-specific fields"""
    print("\n\n=== Example 4: Dynamic Fields ===\n")
    
    class CustomDataSource(DemoDataSource):
        def get_futures_contract(self, root: str, year: int, month: str) -> pd.DataFrame:
            df = super().get_futures_contract(root, year, month)
            df['vwap'] = (df['high'] + df['low'] + df['close']) / 3
            df['trades'] = np.random.randint(100, 1000, len(df))
            return df

    ds = CustomDataSource()
    wti = Future('CL', datasource=ds)
    
    # Get a contract, which will now have the custom fields
    today = date.today()
    contract = wti.contract(today.year, 'H')
    
    if contract:
        print(f"Accessing dynamic fields for {contract}:")
        print(f"VWAP: ${contract.vwap.iloc[-1]:.2f}")
        print(f"Number of trades: {contract.trades.iloc[-1]}")


if __name__ == '__main__':
    example_1_basic_future_usage()
    example_2_notation_and_symbology()
    example_3_continuous_future()
    example_4_dynamic_fields()
