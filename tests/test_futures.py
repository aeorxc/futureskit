"""
Test the Future and ContinuousFuture classes.
"""

import pytest
import pandas as pd
from datetime import date
from futureskit import Future, FuturesContract, ContinuousFuture, RollRule
from futureskit.datasources import FuturesDataSource
from futureskit.notation import ParsedSymbol


# ==================== Mock Data Sources ====================

class MockDataSource:
    """Mock data source that provides various custom fields."""
    
    def get_contract_chain(self, root: str):
        """Provides a mock chain of contracts."""
        return [{'year': 2026, 'month_code': 'H'}]

    def get_futures_contract(self, root: str, year: int, month: str):
        """Return price data with a mix of standard and custom fields."""
        data = pd.DataFrame({
            'open': [100.0], 'high': [102.0], 'low': [99.0], 'close': [101.0],
            'volume': [10000], 'open_interest': [50000], 'settle': [101.1],
            'vwap': [100.5], 'trades': [500], 'implied_volatility': [0.25],
        })
        data.index = pd.to_datetime(['2026-01-20'])
        return data
    
    def get_contract_specs(self, root: str, exchange: str = None):
        """Return contract specs with custom fields."""
        return {
            'tick_size': 0.01, 'contract_size': 1000, 'currency': 'USD',
            'first_notice_date': '2026-02-25', 'exchange_code': 'NYMEX',
            'delivery_location': 'Cushing, OK', 'initial_margin': 5000,
        }


class MockDataSourceFull(FuturesDataSource):
    """Full mock datasource that provides contract chain"""
    
    def get_contract_chain(self, root_symbol: str):
        """Return some test contracts"""
        contracts = []
        for i, month_code in enumerate(['F', 'G', 'H', 'J', 'K', 'M']):
            contract = FuturesContract(
                root_symbol=root_symbol,
                year=2026,
                month_code=month_code,
                datasource=self
            )
            contracts.append(contract)
        return contracts
    
    def get_futures_contract(self, root_symbol: str, year: int, month_code: str):
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        return pd.DataFrame({
            'close': [100, 101, 102, 101, 100],
            'volume': [1000, 1100, 1200, 1100, 1000]
        }, index=dates)
    
    def get_contract_specs(self, root_symbol: str, exchange: str = None):
        return {'tick_size': 0.01}
    
    # Implement other abstract methods
    def series(self, symbols, **kwargs):
        return pd.DataFrame()
    
    def curve(self, symbols, **kwargs):
        return pd.DataFrame()
    
    def contracts(self, symbols, **kwargs):
        return pd.DataFrame()


class MockDataSourceNoChainMethod:
    """Mock datasource without get_contract_chain method"""
    pass


# ==================== Fixtures ====================

@pytest.fixture
def future_contract():
    """Provides a fully-loaded FuturesContract instance for testing."""
    ds = MockDataSource()
    future = Future('CL', datasource=ds)
    contract = future.contract(2026, 'H')
    assert contract is not None, "Test setup failed: Contract could not be retrieved."
    return contract


# ==================== Future Tests ====================

class TestFuture:
    """Test the Future class."""

    def test_basic_creation(self):
        """Test creating a Future object"""
        datasource = MockDataSourceFull()
        future = Future('CL', datasource=datasource)
        
        assert future.root_symbol == 'CL'
        assert future.datasource == datasource
        assert len(future.chain) == 6
    
    def test_datasource_without_chain_method(self):
        """Test fallback when datasource doesn't have get_contract_chain"""
        datasource = MockDataSourceNoChainMethod()
        future = Future('CL', datasource=datasource)
        
        # Should create empty chain with warning
        assert len(future.chain) == 0
    
    def test_load_chain_with_dict_contracts(self):
        """Test _load_chain when datasource returns dicts"""
        class DictDataSource:
            def get_contract_chain(self, root_symbol):
                return [
                    {'year': 2026, 'month_code': 'F'},
                    {'year': 2026, 'month_code': 'G'},
                ]
        
        datasource = DictDataSource()
        future = Future('CL', datasource=datasource)
        
        assert len(future.chain) == 2
        assert future.chain.contracts[0].year == 2026
        assert future.chain.contracts[0].month_code == 'F'

    def test_future_factory(self, future_contract):
        """Test that the Future object correctly creates FuturesContract objects."""
        assert isinstance(future_contract, FuturesContract)
        assert future_contract.root_symbol == 'CL'
        assert future_contract.year == 2026
        assert future_contract.month_code == 'H'
    
    def test_contract_method(self):
        """Test getting specific contract"""
        datasource = MockDataSourceFull()
        future = Future('CL', datasource=datasource)
        
        # Get existing contract
        contract = future.contract(2026, 'H')
        assert contract is not None
        assert contract.month_code == 'H'
        assert contract.year == 2026
        
        # Get non-existing contract
        contract = future.contract(2027, 'Z')
        assert contract is None
    
    def test_getitem_notation(self):
        """Test shorthand notation access"""
        datasource = MockDataSourceFull()
        future = Future('CL', datasource=datasource)
        
        # Valid notation
        contract = future['H26']
        assert contract is not None
        assert contract.month_code == 'H'
        assert contract.year == 2026
        
        # Invalid notation (returns None)
        contract = future['invalid']
        assert contract is None
        
        # Future year
        contract = future['Z99']
        assert contract is None  # Not in chain

    
    def test_continuous_method(self):
        """Test creating continuous futures"""
        datasource = MockDataSourceFull()
        future = Future('CL', datasource=datasource)
        
        # Default continuous
        continuous = future.continuous()
        assert isinstance(continuous, ContinuousFuture)
        assert continuous.future == future
        assert continuous.depth == 1
        
        # With parameters
        continuous = future.continuous(
            roll='volume',
            offset=-10,
            adjust='proportional',
            depth=2
        )
        assert continuous.roll_rule == RollRule.VOLUME
        assert continuous.offset == -10
        assert continuous.adjust == 'proportional'
        assert continuous.depth == 3  # depth + 1
    
    def test_repr(self):
        """Test string representation"""
        datasource = MockDataSourceFull()
        future = Future('CL', datasource=datasource)
        
        assert repr(future) == "Future('CL', contracts=6)"


# ==================== ContinuousFuture Tests ====================

class TestContinuousFuture:
    """Test ContinuousFuture class"""
    
    def test_initialization(self):
        """Test ContinuousFuture initialization"""
        datasource = MockDataSourceFull()
        future = Future('CL', datasource=datasource)
        
        # Test with various roll rules
        continuous = ContinuousFuture(future, roll='volume')
        assert continuous.roll_rule == RollRule.VOLUME
        
        continuous = ContinuousFuture(future, roll='open_interest')
        assert continuous.roll_rule == RollRule.OPEN_INTEREST
        
        continuous = ContinuousFuture(future, roll='oi')  # Alias
        assert continuous.roll_rule == RollRule.OPEN_INTEREST
        
        continuous = ContinuousFuture(future, roll='calendar')
        assert continuous.roll_rule == RollRule.CALENDAR
        
        continuous = ContinuousFuture(future, roll='first_notice')
        assert continuous.roll_rule == RollRule.FIRST_NOTICE
        
        continuous = ContinuousFuture(future, roll='last_trading')
        assert continuous.roll_rule == RollRule.LAST_TRADING
        
        # Test with RollRule enum directly
        continuous = ContinuousFuture(future, roll=RollRule.VOLUME)
        assert continuous.roll_rule == RollRule.VOLUME
        
        # Default roll rule
        continuous = ContinuousFuture(future, roll='unknown')
        assert continuous.roll_rule == RollRule.CALENDAR
    
    def test_evaluate_with_dates(self):
        """Test evaluate with custom date range"""
        datasource = MockDataSourceFull()
        future = Future('CL', datasource=datasource)
        continuous = future.continuous()
        
        # Test with specific dates
        start = date(2023, 1, 1)
        end = date(2023, 12, 31)
        result = continuous.evaluate(start_date=start, end_date=end)
        assert isinstance(result, pd.DataFrame)
    
    def test_evaluate_placeholder(self):
        """Test evaluate method (currently placeholder)"""
        datasource = MockDataSourceFull()
        future = Future('CL', datasource=datasource)
        continuous = future.continuous()
        
        # Should return a DataFrame (could be empty or have data)
        result = continuous.evaluate()
        assert isinstance(result, pd.DataFrame)
    
    def test_build_series_segments_with_empty_schedule(self):
        """Test _build_series_segments with empty roll schedule"""
        datasource = MockDataSourceFull()
        future = Future('CL', datasource=datasource)
        continuous = future.continuous()
        
        # Directly test the internal method
        segments = continuous._build_series_segments(date.today(), date.today())
        assert isinstance(segments, list)
        
        # Should have one segment with active contract
        if segments:
            assert len(segments) == 1
            assert len(segments[0]) == 3  # (start_date, end_date, contract)
    
    def test_repr(self):
        """Test string representation"""
        datasource = MockDataSourceFull()
        future = Future('CL', datasource=datasource)
        continuous = future.continuous(roll='volume', depth=2)
        
        assert repr(continuous) == "ContinuousFuture('CL', roll='v', depth=2)"


# ==================== FuturesContract Tests (mixed access) ====================

class TestFuturesContractAccess:
    """Test the FuturesContract data access features."""

    def test_standard_fields_work(self, future_contract):
        """Test that standard fields work as expected on the contract."""
        assert future_contract.close.iloc[0] == 101.0
        assert future_contract.volume.iloc[0] == 10000
        assert future_contract.tick_size == 0.01
        assert future_contract.currency == 'USD'

    def test_custom_price_fields(self, future_contract):
        """Test accessing custom price series fields on the contract."""
        assert future_contract.vwap.iloc[0] == 100.5
        assert future_contract.trades.iloc[0] == 500
        assert future_contract.implied_volatility.iloc[0] == 0.25

    def test_custom_metadata_fields(self, future_contract):
        """Test accessing custom metadata fields on the contract."""
        assert future_contract.exchange_code == 'NYMEX'
        assert future_contract.delivery_location == 'Cushing, OK'
        assert future_contract.initial_margin == 5000

    def test_dictionary_access(self, future_contract):
        """Test dictionary-style field access on the contract."""
        assert future_contract['close'].iloc[0] == 101.0
        assert future_contract['vwap'].iloc[0] == 100.5
        assert future_contract['tick_size'] == 0.01

    def test_date_field_conversion(self, future_contract):
        """Test automatic date conversion in metadata."""
        assert isinstance(future_contract.first_notice_date, date)
        assert future_contract.first_notice_date == date(2026, 2, 25)

    def test_missing_field_error(self, future_contract):
        """Test proper error for missing fields."""
        with pytest.raises(AttributeError, match="no attribute 'nonexistent'"):
            _ = future_contract.nonexistent
        with pytest.raises(KeyError, match="Field 'nonexistent' not found"):
            _ = future_contract['nonexistent']


# ==================== Edge Cases ====================

class TestNotationEdgeCases:
    """Test edge cases in notation parsing (related to Future usage)"""
    
    def test_partial_symbol_to_string(self):
        """Test to_string() for partially parsed symbols"""
        from futureskit import ParsedSymbol
        
        # Just root
        parsed = ParsedSymbol(root='BRN')
        assert parsed.to_string() == 'BRN'
        
        # Root and year
        parsed = ParsedSymbol(root='BRN', year=2026)
        assert parsed.to_string() == 'BRN_2026'
        
        # Root and month (unusual but possible)
        parsed = ParsedSymbol(root='BRN', month='F')
        assert parsed.to_string() == 'BRNF'