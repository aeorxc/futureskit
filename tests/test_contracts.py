"""
Tests for contracts module
"""

import pytest
import pandas as pd
from datetime import date
from futureskit import FuturesContract, ContractChain, MONTH_CODES
from futureskit.datasources import FuturesDataSource


class MockDataSource(FuturesDataSource):
    """Mock datasource for testing"""
    
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
    
    def get_futures_contract(self, root_symbol: str, year: int, month_code: str) -> pd.DataFrame:
        if self.should_fail:
            raise Exception("Mock failure")
        
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        return pd.DataFrame({
            'close': [100, 101, 102, 101, 100],
            'volume': [1000, 1100, 1200, 1100, 1000]
        }, index=dates)
    
    def get_contract_specs(self, root_symbol: str, exchange: str = None) -> dict:
        if self.should_fail:
            raise Exception("Mock failure")
        
        return {
            'tick_size': 0.01,
            'contract_size': 1000,
            'currency': 'USD'
        }
    
    # Implement other abstract methods
    def series(self, symbols, **kwargs):
        return pd.DataFrame()
    
    def curve(self, symbols, **kwargs):
        return pd.DataFrame()
    
    def contracts(self, symbols, **kwargs):
        return pd.DataFrame()
    
    def get_contract_chain(self, root_symbol):
        return []
    
    def __repr__(self):
        return "<MockDataSource>"


class TestFuturesContract:
    """Test FuturesContract class"""
    
    def test_basic_creation(self):
        """Test creating a basic contract"""
        contract = FuturesContract('BRN', 2026, 'F')
        assert contract.root_symbol == 'BRN'
        assert contract.year == 2026
        assert contract.month_code == 'F'
    
    def test_delivery_date(self):
        """Test delivery date calculation"""
        contract = FuturesContract('CL', 2026, 'H')  # March
        assert contract.delivery_date == date(2026, 3, 1)
    
    def test_month_num(self):
        """Test month number property"""
        contract = FuturesContract('CL', 2026, 'H')
        assert contract.month_num == 3
        
        # Test invalid month code
        contract = FuturesContract('CL', 2026, 'A')
        assert contract.month_num == 0
    
    def test_to_canonical(self):
        """Test canonical string format"""
        contract = FuturesContract('BRN', 2026, 'F')
        assert contract.to_canonical() == 'BRN_2026F'
    
    def test_to_short_year(self):
        """Test short year format"""
        contract = FuturesContract('BRN', 2026, 'F')
        assert contract.to_short_year() == 'BRN26F'
        
        # Test year 2000
        contract = FuturesContract('CL', 2000, 'H')
        assert contract.to_short_year() == 'CL00H'
    
    def test_str_repr(self):
        """Test string representations"""
        contract = FuturesContract('BRN', 2026, 'F')
        assert str(contract) == 'BRN_2026F'
        assert repr(contract) == "FuturesContract('BRN', 2026, 'F')"
    
    def test_comparison_operators(self):
        """Test equality and comparison"""
        c1 = FuturesContract('BRN', 2026, 'F')
        c2 = FuturesContract('BRN', 2026, 'F')
        c3 = FuturesContract('BRN', 2026, 'G')
        c4 = FuturesContract('CL', 2026, 'F')
        
        # Equality
        assert c1 == c2
        assert c1 != c3
        assert c1 != c4
        assert c1 != "not a contract"
        
        # Less than (by delivery date)
        assert c1 < c3  # Jan < Feb
        assert not c3 < c1
        
        # Test with non-contract
        assert c1.__lt__("not a contract") == NotImplemented
    
    def test_data_loading(self):
        """Test data loading from datasource"""
        datasource = MockDataSource()
        contract = FuturesContract('BRN', 2026, 'F', datasource=datasource)
        
        # Access price data (triggers load)
        close_prices = contract.close
        assert len(close_prices) == 5
        assert close_prices.iloc[0] == 100
        
        # Access metadata
        assert contract.tick_size == 0.01
        assert contract.contract_size == 1000
    
    def test_data_loading_failure(self):
        """Test data loading with errors"""
        datasource = MockDataSource(should_fail=True)
        contract = FuturesContract('BRN', 2026, 'F', datasource=datasource)
        
        # Should not raise, just log warning
        contract._load_data()
        
        # Data should remain unloaded
        assert contract._price_data is None
        assert contract._metadata == {}
    
    def test_getattr_fallback(self):
        """Test attribute access for missing fields"""
        contract = FuturesContract('BRN', 2026, 'F')
        
        with pytest.raises(AttributeError, match="no attribute 'missing_field'"):
            _ = contract.missing_field
    
    def test_getitem_access(self):
        """Test dictionary-style access"""
        datasource = MockDataSource()
        contract = FuturesContract('BRN', 2026, 'F', datasource=datasource)
        
        # Access price data
        assert len(contract['close']) == 5
        
        # Access metadata
        assert contract['tick_size'] == 0.01
        
        # Missing field
        with pytest.raises(KeyError, match="Field 'missing' not found"):
            _ = contract['missing']
    
    def test_date_conversion_in_metadata(self):
        """Test automatic date conversion for metadata fields"""
        contract = FuturesContract('BRN', 2026, 'F')
        contract._metadata = {
            'expiry_date': '2026-01-25',
            'first_notice_date': '2026-01-20',
            'regular_field': 'not a date'
        }
        
        # Date fields should be converted
        assert contract.expiry_date == date(2026, 1, 25)
        assert contract.first_notice_date == date(2026, 1, 20)
        
        # Non-date fields should remain as-is
        assert contract.regular_field == 'not a date'


class TestContractChain:
    """Test ContractChain class"""
    
    def setup_method(self):
        """Create test contracts"""
        self.contracts = [
            FuturesContract('BRN', 2026, 'H'),  # March
            FuturesContract('BRN', 2026, 'F'),  # January
            FuturesContract('BRN', 2026, 'M'),  # June
            FuturesContract('BRN', 2026, 'G'),  # February
        ]
    
    def test_auto_sorting(self):
        """Test that contracts are automatically sorted by delivery date"""
        chain = ContractChain('BRN', self.contracts)
        
        # Should be sorted: F, G, H, M (Jan, Feb, Mar, Jun)
        assert chain.contracts[0].month_code == 'F'
        assert chain.contracts[1].month_code == 'G'
        assert chain.contracts[2].month_code == 'H'
        assert chain.contracts[3].month_code == 'M'
    
    def test_get_contract(self):
        """Test getting specific contract"""
        chain = ContractChain('BRN', self.contracts)
        
        # Get existing contract
        contract = chain.get_contract(2026, 'H')
        assert contract is not None
        assert contract.month_code == 'H'
        
        # Get non-existing contract
        contract = chain.get_contract(2026, 'Z')
        assert contract is None
    
    def test_get_front_month(self):
        """Test getting front month contract"""
        chain = ContractChain('BRN', self.contracts)
        
        # Test with specific date
        front = chain.get_front_month(as_of=date(2026, 2, 15))
        assert front.month_code == 'H'  # March is front month
        
        # Test with date after all contracts
        front = chain.get_front_month(as_of=date(2026, 7, 1))
        assert front is None
    
    def test_get_nth_contract(self):
        """Test getting nth contract"""
        chain = ContractChain('BRN', self.contracts)
        
        # Get various positions
        first = chain.get_nth_contract(1, as_of=date(2025, 12, 1))
        assert first.month_code == 'F'  # January
        
        third = chain.get_nth_contract(3, as_of=date(2025, 12, 1))
        assert third.month_code == 'H'  # March
        
        # Beyond available contracts
        beyond = chain.get_nth_contract(10, as_of=date(2025, 12, 1))
        assert beyond is None
    
    def test_len_and_iter(self):
        """Test length and iteration"""
        chain = ContractChain('BRN', self.contracts)
        
        assert len(chain) == 4
        
        # Test iteration
        months = [c.month_code for c in chain]
        assert months == ['F', 'G', 'H', 'M']
    
    def test_getitem(self):
        """Test index access"""
        chain = ContractChain('BRN', self.contracts)
        
        assert chain[0].month_code == 'F'
        assert chain[-1].month_code == 'M'
        
        # Test slicing
        subset = chain[1:3]
        assert len(subset) == 2
        assert subset[0].month_code == 'G'