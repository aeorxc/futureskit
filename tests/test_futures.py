"""
Test the Future and FuturesContract classes.
"""

import pytest
import pandas as pd
from datetime import date
from futureskit import Future, FuturesContract


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


@pytest.fixture
def future_contract():
    """Provides a fully-loaded FuturesContract instance for testing."""
    ds = MockDataSource()
    future = Future('CL', datasource=ds)
    contract = future.contract(2026, 'H')
    assert contract is not None, "Test setup failed: Contract could not be retrieved."
    return contract


class TestFuturesModel:
    """Test the new Future and FuturesContract object model."""

    def test_future_factory(self, future_contract):
        """Test that the Future object correctly creates FuturesContract objects."""
        assert isinstance(future_contract, FuturesContract)
        assert future_contract.root_symbol == 'CL'
        assert future_contract.year == 2026
        assert future_contract.month_code == 'H'

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

    def test_shorthand_access(self):
        """Test the __getitem__ shorthand on the Future object."""
        ds = MockDataSource()
        future = Future('CL', datasource=ds)
        contract = future['H26']
        assert contract is not None
        assert contract.year == 2026
        assert contract.month_code == 'H'
        assert contract.close.iloc[0] == 101.0
