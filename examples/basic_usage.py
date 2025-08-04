"""
Basic usage examples for futureskit

This demonstrates all major features of FuturesKit including:
- Parsing futures notation
- Symbol conversion between vendors  
- Working with Future and FuturesContract objects
- Using the FuturesDataSource interface
- Continuous futures concepts
"""

import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import List, Optional, Union
from futureskit import (
    Future, ContinuousFuture, FuturesContract, ContractChain,
    FuturesNotation, SymbologyConverter,
    FuturesDataSource, MONTH_CODES
)


# ==================== Data Source Implementation ====================

class DemoDataSource(FuturesDataSource):
    """
    Example implementation of FuturesDataSource for demonstration.
    
    This shows how a real data provider would implement the interface.
    In production, this would fetch from APIs, databases, etc.
    """
    
    def __init__(self):
        self.notation = FuturesNotation()
        # Cache for consistent data
        self._price_cache = {}
    
    def series(self, 
               symbols: Union[str, List[str]], 
               fields: Optional[List[str]] = None,
               start_date: Optional[Union[date, str]] = None,
               **kwargs) -> pd.DataFrame:
        """Get time series data for symbols."""
        if isinstance(symbols, str):
            symbols = [symbols]
        
        # Default date range
        end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)
        
        # Convert string dates
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date).date()
        
        # Default fields
        if fields is None:
            fields = ['close', 'volume', 'open_interest']
        
        # Generate date range
        dates = pd.date_range(start=start_date, end=end_date, freq='B')
        
        # Generate data for each symbol
        all_data = {}
        for symbol in symbols:
            # Use consistent random seed for each symbol
            np.random.seed(hash(symbol) % (2**32 - 1))
            
            for field in fields:
                col_name = f"{symbol}_{field}"
                
                if field == 'close' or field == 'settlement':
                    # Generate price data
                    returns = np.random.randn(len(dates)) * 0.01
                    prices = 100 * np.exp(np.cumsum(returns))
                    all_data[col_name] = prices
                    
                elif field == 'volume':
                    all_data[col_name] = np.random.randint(1000, 10000, len(dates))
                elif field == 'open_interest':
                    all_data[col_name] = np.random.randint(50000, 100000, len(dates))
        
        return pd.DataFrame(all_data, index=dates)
    
    def curve(self, 
              symbols: Union[str, List[str]], 
              curve_dates: Optional[Union[date, str, List[date], List[str]]] = None,
              fields: Optional[List[str]] = None,
              **kwargs) -> pd.DataFrame:
        """Get forward curve data."""
        if isinstance(symbols, str):
            symbols = [symbols]
        
        # Handle curve_dates
        if curve_dates is None:
            curve_dates = date.today()
        
        # Normalize to list for consistent handling
        if not isinstance(curve_dates, list):
            curve_dates = [curve_dates]
        
        # Convert string dates
        normalized_dates = []
        for d in curve_dates:
            if isinstance(d, str):
                normalized_dates.append(pd.to_datetime(d).date())
            else:
                normalized_dates.append(d)
        
        if fields is None:
            fields = ['settlement']
        
        all_curves = []
        
        for curve_date in normalized_dates:
            for symbol in symbols:
                # Get contracts for this symbol
                contracts = self.get_contract_chain(symbol)
                
                for i, contract in enumerate(contracts[:12]):  # First 12 months
                    contract_data = {
                        'curve_date': curve_date,
                        'symbol': symbol,
                        'contract': contract.to_canonical(),
                        'delivery_date': contract.delivery_date,
                        'month_code': contract.month_code,
                        'year': contract.year
                    }
                    
                    # Add field data with contango
                    np.random.seed(hash(symbol) % (2**32 - 1))
                    base_price = 100 + np.random.randn() * 10
                    
                    for field in fields:
                        if field == 'settlement':
                            # Add contango
                            contract_data[field] = base_price + i * 0.15
                        elif field == 'volume':
                            # Volume decreases for further contracts
                            contract_data[field] = max(100, 10000 - i * 1000)
                    
                    all_curves.append(contract_data)
        
        return pd.DataFrame(all_curves)
    
    def contracts(self,
                  symbols: Union[str, List[str]],
                  start_date: Optional[Union[date, str]] = None,
                  start_year: Optional[int] = None,
                  end_year: Optional[int] = None,
                  fields: Optional[List[str]] = None,
                  **kwargs) -> pd.DataFrame:
        """Get historical data for contract months."""
        if isinstance(symbols, str):
            symbols = [symbols]
        
        # Default year range
        if end_year is None:
            end_year = date.today().year
        if start_year is None:
            start_year = end_year - 1
        
        # Default fields
        if fields is None:
            fields = ['settlement', 'volume']
        
        # Get contract chain for each symbol
        all_contracts = []
        for symbol in symbols:
            chain = self.get_contract_chain(symbol)
            for contract in chain:
                if start_year <= contract.year <= end_year:
                    all_contracts.append(contract.to_canonical())
        
        # Get series data for all contracts
        if all_contracts:
            return self.series(all_contracts, fields=fields, start_date=start_date)
        
        return pd.DataFrame()
    
    def get_contract_chain(self, root_symbol: str) -> List[FuturesContract]:
        """Get available contracts for a commodity."""
        contracts = []
        current_date = date.today()
        
        # Generate monthly contracts for next 24 months
        for i in range(24):
            year = current_date.year
            month = current_date.month + i
            
            # Handle year rollover
            while month > 12:
                month -= 12
                year += 1
            
            # Create contract
            month_code = list(MONTH_CODES.keys())[month - 1]
            delivery_date = date(year, month, 1)
            
            contract = FuturesContract(
                root_symbol=root_symbol,
                year=year,
                month_code=month_code,
                datasource=self  # Important: for lazy loading
            )
            
            # Add optional metadata as attributes (not the computed property)
            contract.first_trade_date = delivery_date - timedelta(days=365)
            contract.last_trade_date = delivery_date - timedelta(days=5)
            contract.expiry_date = delivery_date - timedelta(days=5)
            
            contracts.append(contract)
        
        return contracts
    
    def get_futures_contract(self, root_symbol: str, year: int, month_code: str) -> pd.DataFrame:
        """Get data for a specific contract (used by FuturesContract for lazy loading)."""
        contract_symbol = f"{root_symbol}_{year}{month_code}"
        return self.series(contract_symbol)


# ==================== Example Functions ====================

def example_1_notation_parsing():
    """Example 1: Parsing futures notation"""
    print("=== Example 1: Futures Notation Parsing ===\n")
    
    notation = FuturesNotation()
    
    # Parse different formats
    examples = [
        'BRN_2026F',    # Canonical format
        'BRN26F',       # Short year
        'BRNF26',       # Month first
        'BRN-26F',      # With separator
        'BRN.n.1',      # Continuous front month
        'CL.v.3',       # Continuous third month by volume
    ]
    
    for symbol in examples:
        parsed = notation.parse(symbol)
        print(f"Symbol: {symbol:12} -> Root: {parsed.root}, "
              f"Year: {parsed.year}, Month: {parsed.month}, "
              f"Continuous: {parsed.is_continuous}")
        if parsed.is_continuous:
            print(f"  Roll rule: {parsed.roll_rule}, Index: {parsed.contract_index}")
        if parsed.warnings:
            print(f"  Warnings: {parsed.warnings}")


def example_2_symbol_conversion():
    """Example 2: Converting between vendor formats"""
    print("\n\n=== Example 2: Symbol Conversion ===\n")
    
    notation = FuturesNotation()
    converter = SymbologyConverter()
    
    # Parse a canonical symbol
    parsed = notation.parse('CL_2025H')
    
    print(f"Original: CL_2025H")
    print(f"CME format: {converter.to_cme_format(parsed)}")
    print(f"ICE format: {converter.to_ice_format(parsed)}")
    print(f"Bloomberg format: {converter.to_bloomberg_format(parsed)}")
    print(f"Short year: {converter.to_short_year_format(parsed)}")
    
    # Continuous contract
    continuous = notation.parse('BRN.n.1')
    print(f"\nContinuous: BRN.n.1")
    print(f"Marketplace: {converter.to_marketplace_continuous(continuous)}")


def example_3_futures_objects():
    """Example 3: Working with Future and FuturesContract objects"""
    print("\n\n=== Example 3: Future and Contract Objects ===\n")
    
    # Create data source
    datasource = DemoDataSource()
    
    # Create a Future object
    wti = Future('CL', datasource=datasource)
    print(f"Created Future for {wti.root_symbol}")
    print(f"Available contracts: {len(wti.chain)}")
    
    # Get specific contract
    mar_26 = wti.contract(2026, 'H')
    if mar_26:
        print(f"\nMarch 2026 contract: {mar_26}")
        print(f"Delivery date: {mar_26.delivery_date}")
        print(f"Canonical symbol: {mar_26.to_canonical()}")
        print(f"Short year format: {mar_26.to_short_year()}")
    
    # Use shorthand notation
    jun_25 = wti['M25']
    if jun_25:
        print(f"\nUsing shorthand 'M25': {jun_25.to_canonical()}")
    
    # Get front month
    front = wti.chain.get_front_month()
    if front:
        print(f"\nFront month contract: {front.to_canonical()}")
    
    # Get nth contract
    third = wti.chain.get_nth_contract(3)
    if third:
        print(f"Third month contract: {third.to_canonical()}")


def example_4_data_access():
    """Example 4: Accessing data through FuturesDataSource"""
    print("\n\n=== Example 4: Data Access ===\n")
    
    datasource = DemoDataSource()
    
    # Time series data
    df = datasource.series(
        symbols=['BRN_2026F', 'CL_2026H'],
        fields=['close', 'volume'],
        start_date='2024-01-01'
    )
    print("Time Series Data:")
    print(df.head())
    print(f"Shape: {df.shape}")
    
    # Forward curve
    curve = datasource.curve(
        symbols='BRN',
        curve_dates='2024-01-15',
        fields=['settlement', 'volume']
    )
    print("\n\nForward Curve:")
    print(curve.head())
    
    # Contract history
    contracts_df = datasource.contracts(
        symbols='CL',
        start_year=2024,
        end_year=2025,
        fields=['settlement'],
        start_date='2024-01-01'
    )
    print(f"\n\nContract History Shape: {contracts_df.shape}")
    print(f"Columns: {list(contracts_df.columns)[:5]}...")


def example_5_contract_chain():
    """Example 5: Working with contract chains"""
    print("\n\n=== Example 5: Contract Chains ===\n")
    
    datasource = DemoDataSource()
    
    # Get contract chain
    contracts = datasource.get_contract_chain('BRN')
    print(f"Found {len(contracts)} contracts for BRN")
    
    # Examine contracts
    print("\nNext 6 contracts:")
    for contract in contracts[:6]:
        print(f"  {contract.to_canonical()}: "
              f"Delivery {contract.delivery_date.strftime('%Y-%m')}, "
              f"Last trade {contract.last_trade_date}")
    
    # Filter active contracts
    active = [c for c in contracts if c.last_trade_date > date.today()]
    print(f"\nActive contracts: {len(active)}")


def example_6_continuous_futures():
    """Example 6: Continuous futures concepts"""
    print("\n\n=== Example 6: Continuous Futures ===\n")
    
    datasource = DemoDataSource()
    wti = Future('CL', datasource=datasource)
    
    # Create continuous futures (placeholder implementation)
    continuous = wti.continuous(
        roll='volume',
        offset=-5,
        adjust='back'
    )
    
    print(f"Continuous futures: {continuous}")
    print(f"Roll rule: {continuous.roll_rule}")
    print(f"Depth: {continuous.depth}")
    print(f"Adjustment: {continuous.adjust}")
    
    # Note: evaluate() is not fully implemented yet
    print("\nNote: Full continuous series evaluation is not yet implemented")


def example_7_practical_workflow():
    """Example 7: Practical workflow combining features"""
    print("\n\n=== Example 7: Practical Workflow ===\n")
    
    # Initialize components
    datasource = DemoDataSource()
    notation = FuturesNotation()
    converter = SymbologyConverter()
    
    # User provides a symbol in unknown format
    user_symbol = "BRN26F"
    
    # Parse it
    parsed = notation.parse(user_symbol)
    print(f"User provided: {user_symbol}")
    print(f"Parsed as: {parsed.root} {parsed.year} {parsed.month}")
    
    # Create Future object
    future = Future(parsed.root, datasource=datasource)
    
    # Get the specific contract
    contract = future.contract(parsed.year, parsed.month)
    if contract:
        print(f"\nContract details:")
        print(f"  Canonical: {contract.to_canonical()}")
        print(f"  Delivery: {contract.delivery_date}")
        
        # Convert to different formats for different systems
        print(f"\nSend to different systems:")
        print(f"  CME: {converter.to_cme_format(parsed)}")
        print(f"  Bloomberg: {converter.to_bloomberg_format(parsed)}")
        
        # Get price data
        data = datasource.series(
            contract.to_canonical(),
            fields=['close', 'volume'],
            start_date=date.today() - timedelta(days=5)
        )
        print(f"\nRecent prices:")
        print(data.tail(3))


def main():
    """Run all examples"""
    example_1_notation_parsing()
    example_2_symbol_conversion()
    example_3_futures_objects()
    example_4_data_access()
    example_5_contract_chain()
    example_6_continuous_futures()
    example_7_practical_workflow()
    
    print("\n\n=== Summary ===")
    print("FuturesKit provides:")
    print("1. Notation parsing for various futures formats")
    print("2. Symbol conversion between vendor conventions")
    print("3. First-class Future and FuturesContract objects")
    print("4. Clean data source interface for any provider")
    print("5. Support for continuous futures concepts")
    print("\nSee the documentation for more details!")


if __name__ == '__main__':
    main()